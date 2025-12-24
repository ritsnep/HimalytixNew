from __future__ import annotations

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from accounting.models import Journal, VoucherModeConfig, VoucherProcess
from accounting.services.create_voucher import create_voucher_transaction
from accounting.services.posting_service import PostingService
from accounting.services.voucher_errors import VoucherProcessError, map_exception_to_error
from usermanagement.utils import PermissionUtils


class VoucherOrchestrator:
    def __init__(self, user):
        self.user = user

    def _validate_inventory_metadata(self, journal, config):
        if not getattr(config, "affects_inventory", False):
            return
        metadata = journal.metadata or {}
        transactions = metadata.get("inventory_transactions") or []
        if not transactions:
            raise VoucherProcessError("INV-002", "Missing inventory transactions metadata.")
        for idx, txn in enumerate(transactions, start=1):
            if not txn.get("product_id"):
                raise VoucherProcessError("INV-002", f"Inventory transaction {idx} missing product_id.")
            if not txn.get("warehouse_id"):
                raise VoucherProcessError("INV-004", f"Inventory transaction {idx} missing warehouse_id.")
            if not txn.get("uom_id"):
                raise VoucherProcessError("INV-011", f"Inventory transaction {idx} missing uom_id.")
            if not txn.get("quantity"):
                raise VoucherProcessError("INV-005", f"Inventory transaction {idx} missing quantity.")
            if not txn.get("journal_line_id"):
                raise VoucherProcessError("INV-005", f"Inventory transaction {idx} missing journal_line_id.")
            if not txn.get("voucher_id") or not txn.get("journal_id"):
                raise VoucherProcessError("INV-005", f"Inventory transaction {idx} missing voucher/journal id.")
            txn_type = (txn.get("txn_type") or "issue").lower()
            if txn_type == "receipt":
                if not txn.get("unit_cost"):
                    raise VoucherProcessError("INV-006", f"Inventory transaction {idx} missing unit_cost.")
                if not txn.get("grir_account_id"):
                    raise VoucherProcessError("INV-007", f"Inventory transaction {idx} missing grir_account_id.")
            else:
                if not txn.get("cogs_account_id"):
                    raise VoucherProcessError("INV-008", f"Inventory transaction {idx} missing cogs_account_id.")

    def create_and_process(self, config, header_data, lines_data, action: str, *, idempotency_key: str | None = None, last_modified_at: str | None = None):
        commit_type = "save"
        if action == "submit_voucher":
            commit_type = "submit"
        elif action == "post_voucher":
            commit_type = "post"

        return create_voucher_transaction(
            user=self.user,
            config_id=config.pk,
            header_data=header_data,
            lines_data=lines_data,
            commit_type=commit_type,
            idempotency_key=idempotency_key,
            last_modified_at=last_modified_at,
        )

    def process(
        self,
        voucher_id: int,
        commit_type: str = "post",
        actor=None,
        idempotency_key: str | None = None,
        config: VoucherModeConfig | None = None,
    ):
        actor = actor or self.user
        attempt = VoucherProcess.objects.create(
            journal_id=voucher_id,
            journal_id_snapshot=voucher_id,
            organization=actor.organization if actor and getattr(actor, "organization", None) else Journal.objects.get(pk=voucher_id).organization,
            actor=actor,
            commit_type=commit_type,
            idempotency_key=idempotency_key,
            saved_status="done",
            journal_status="done",
            gl_status="pending",
            inventory_status="pending",
        )
        start = timezone.now()

        try:
            with transaction.atomic():
                journal = (
                    Journal.objects.select_for_update()
                    .select_related("organization", "journal_type", "period")
                    .get(pk=voucher_id)
                )

                if idempotency_key:
                    if journal.idempotency_key and journal.idempotency_key != idempotency_key:
                        raise VoucherProcessError("VCH-409", "Idempotency key mismatch for voucher.")
                    if not journal.idempotency_key:
                        journal.idempotency_key = idempotency_key
                        journal.save(update_fields=["idempotency_key"])

                if journal.status == "posted":
                    attempt.status = "succeeded"
                    attempt.gl_status = "done"
                    attempt.inventory_status = "done"
                    attempt.ended_at = timezone.now()
                    attempt.duration_ms = int((attempt.ended_at - start).total_seconds() * 1000)
                    attempt.save(update_fields=["status", "gl_status", "inventory_status", "ended_at", "duration_ms"])
                    journal.process_attempt = attempt
                    return journal

                if VoucherProcess.objects.filter(
                    journal=journal, status="processing"
                ).exclude(attempt_id=attempt.attempt_id).exists():
                    raise VoucherProcessError("VCH-409", "Voucher is already being processed.")

                if config is None:
                    config = VoucherModeConfig.objects.filter(
                        organization=journal.organization,
                        journal_type=journal.journal_type,
                        is_active=True,
                    ).first()

                requires_approval = bool(getattr(config, "requires_approval", False)) if config else False
                can_post = True
                if actor and journal.organization:
                    can_post = PermissionUtils.has_permission(
                        actor, journal.organization, "accounting", "journal", "post_journal"
                    )
                can_approve = False
                if actor and journal.organization:
                    can_approve = PermissionUtils.has_permission(
                        actor, journal.organization, "accounting", "journal", "approve_journal"
                    )

                if commit_type in ("submit",) or (requires_approval and not can_post):
                    if journal.status != "awaiting_approval":
                        journal.status = "awaiting_approval"
                        journal.save(update_fields=["status"])
                    attempt.status = "succeeded"
                    attempt.gl_status = "pending"
                    attempt.inventory_status = "pending"
                    attempt.ended_at = timezone.now()
                    attempt.duration_ms = int((attempt.ended_at - start).total_seconds() * 1000)
                    attempt.save(update_fields=["status", "gl_status", "inventory_status", "ended_at", "duration_ms"])
                    journal.process_attempt = attempt
                    return journal

                attempt.gl_status = "in_progress"
                attempt.save(update_fields=["gl_status"])
                if journal.status == "awaiting_approval":
                    if requires_approval and not can_approve and not can_post:
                        raise VoucherProcessError(
                            "VCH-403",
                            "Approval required before posting this voucher.",
                        )
                    # Allow direct post users or approvers to advance status.
                    journal.status = "approved"
                    journal.save(update_fields=["status"])
                if config:
                    self._validate_inventory_metadata(journal, config)
                posting_service = PostingService(actor)
                journal = posting_service.post(journal)

                attempt.status = "succeeded"
                attempt.gl_status = "done"
                attempt.inventory_status = "done"
                attempt.ended_at = timezone.now()
                attempt.duration_ms = int((attempt.ended_at - start).total_seconds() * 1000)
                attempt.save(update_fields=["status", "gl_status", "inventory_status", "ended_at", "duration_ms"])
                journal.process_attempt = attempt
                return journal
        except VoucherProcessError as exc:
            attempt.status = "failed"
            attempt.error_code = exc.code
            attempt.error_details = {"message": exc.message}
            attempt.ended_at = timezone.now()
            attempt.duration_ms = int((attempt.ended_at - start).total_seconds() * 1000)
            step = "save"
            if exc.code.startswith("INV"):
                step = "inventory"
            elif exc.code.startswith("GL"):
                step = "gl"
            if step == "inventory":
                attempt.inventory_status = "failed"
                attempt.gl_status = "done"
            elif step == "gl":
                attempt.gl_status = "failed"
            else:
                attempt.saved_status = "failed"
            attempt.save(
                update_fields=[
                    "status",
                    "error_code",
                    "error_details",
                    "ended_at",
                    "duration_ms",
                    "saved_status",
                    "gl_status",
                    "inventory_status",
                ]
            )
            raise
        except ValidationError as exc:
            mapped = map_exception_to_error(exc)
            attempt.status = "failed"
            attempt.error_code = mapped.code
            attempt.error_details = {"message": mapped.message}
            attempt.ended_at = timezone.now()
            attempt.duration_ms = int((attempt.ended_at - start).total_seconds() * 1000)
            attempt.gl_status = "failed"
            attempt.save(
                update_fields=[
                    "status",
                    "error_code",
                    "error_details",
                    "ended_at",
                    "duration_ms",
                    "gl_status",
                ]
            )
            raise mapped from exc
