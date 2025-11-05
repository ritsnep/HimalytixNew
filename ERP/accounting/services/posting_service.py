from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Optional

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from accounting.models import (
    AccountingPeriod,
    ChartOfAccount,
    GeneralLedger,
    Journal,
    JournalLine,
)
from accounting.utils.audit import log_audit_event
from usermanagement.models import CustomUser, Organization
from usermanagement.utils import PermissionUtils

logger = logging.getLogger(__name__)


class PostingService:
    """
    Handles posting and reversal of journals while enforcing validation,
    permissions, and accounting invariants.
    """

    # Error Messages
    ERR_PERIOD_CLOSED = "Posting date falls into a closed accounting period."
    ERR_IMBALANCED_JOURNAL = "Journal is out of balance. Total debits must equal total credits."
    ERR_PERMISSION_DENIED = "You do not have permission to perform this action."
    ERR_JOURNAL_LOCKED = "Journal is locked and cannot be modified."
    ERR_INVALID_STATUS_TRANSITION = "Invalid journal status transition from {current_status} to {new_status}."
    ERR_REVERSAL_NOT_ALLOWED = "Only posted journals can be reversed."
    ERR_REVERSAL_ALREADY_EXISTS = "This journal already has a reversal entry."
    ERR_VOUCHER_TYPE_VALIDATION = "Voucher type specific validation failed: {reason}"
    ERR_MISSING_DIMENSION = "Required dimension {dimension} is missing for account {account_code}."
    ERR_PERIOD_NOT_CLOSED = "Period is not closed and cannot be reopened."

    # Allowed Status Transitions
    ALLOWED_TRANSITIONS = {
        "draft": ["awaiting_approval", "posted"],
        "awaiting_approval": ["approved", "rejected", "draft"],
        "approved": ["posted", "rejected", "draft"],
        "posted": ["reversed"],
        "rejected": ["draft"],
        "reversed": [],
    }

    # Permissions required for each transition (module, entity, action)
    PERMISSION_MAP = {
        "awaiting_approval": ("accounting", "journal", "submit_journal"),
        "approved": ("accounting", "journal", "approve_journal"),
        "posted": ("accounting", "journal", "post_journal"),
        "reversed": ("accounting", "journal", "reverse_journal"),
        "rejected": ("accounting", "journal", "reject_journal"),
        "draft": ("accounting", "journal", "change"),
    }

    QUANTIZE_TARGET = Decimal("0.0000")

    def __init__(self, user: Optional[CustomUser]):
        self.user = user
        if user is not None:
            self.organization = getattr(
                user,
                "get_active_organization",
                lambda: getattr(user, "organization", None),
            )()
        else:
            self.organization = None

    # ---------------------------------------------------------------------
    # Permission & validation helpers
    # ---------------------------------------------------------------------
    def _check_permission(
        self,
        permission: tuple[str, str, str],
        organization: Optional[Organization] = None,
    ) -> None:
        if self.user is None:
            return
        organization = organization or self.organization
        if not PermissionUtils.has_permission(self.user, organization, *permission):
            raise PermissionDenied(self.ERR_PERMISSION_DENIED)

    def _validate_status_transition(
        self,
        journal: Journal,
        new_status: str,
        enforce_permission: bool = True,
    ) -> None:
        allowed = self.ALLOWED_TRANSITIONS.get(journal.status, [])
        if new_status not in allowed:
            raise ValidationError(
                self.ERR_INVALID_STATUS_TRANSITION.format(
                    current_status=journal.status,
                    new_status=new_status,
                )
            )
        if enforce_permission:
            permission = self.PERMISSION_MAP.get(new_status)
            if permission:
                self._check_permission(permission, journal.organization)

    def _validate_period_control(self, journal: Journal) -> None:
        if not AccountingPeriod.is_date_in_open_period(journal.organization, journal.journal_date):
            raise ValidationError(self.ERR_PERIOD_CLOSED)

    def _validate_double_entry_invariant(self, journal: Journal) -> None:
        journal.update_totals()
        debit = journal.total_debit or Decimal("0")
        credit = journal.total_credit or Decimal("0")
        if (debit - credit).quantize(self.QUANTIZE_TARGET) != Decimal("0.0000"):
            raise ValidationError(self.ERR_IMBALANCED_JOURNAL)

    def _validate_voucher_type_rules(
        self,
        journal: Journal,
        lines: Iterable[JournalLine],
    ) -> None:
        for line in lines:
            account = line.account
            if account.organization_id != journal.organization_id:
                raise ValidationError(
                    self.ERR_VOUCHER_TYPE_VALIDATION.format(
                        reason="Lines cannot reference accounts from another organization."
                    )
                )
            if account.require_cost_center and not line.cost_center_id:
                raise ValidationError(
                    self.ERR_MISSING_DIMENSION.format(
                        dimension="Cost Center",
                        account_code=account.account_code,
                    )
                )
            if account.require_project and not line.project_id:
                raise ValidationError(
                    self.ERR_MISSING_DIMENSION.format(
                        dimension="Project",
                        account_code=account.account_code,
                    )
                )
            if account.require_department and not line.department_id:
                raise ValidationError(
                    self.ERR_MISSING_DIMENSION.format(
                        dimension="Department",
                        account_code=account.account_code,
                    )
                )

    def validate(self, journal: Journal, lines: Optional[Iterable[JournalLine]] = None) -> None:
        lines = list(lines) if lines is not None else list(journal.lines.all())
        if not lines:
            raise ValidationError("Journal must contain at least one line.")
        self._validate_period_control(journal)
        self._validate_double_entry_invariant(journal)
        self._validate_voucher_type_rules(journal, lines)

    # ---------------------------------------------------------------------
    # Posting helpers
    # ---------------------------------------------------------------------
    def _prepare_line_amounts(self, line: JournalLine, journal: Journal) -> Decimal:
        debit = (line.debit_amount or Decimal("0")).quantize(self.QUANTIZE_TARGET, rounding=ROUND_HALF_UP)
        credit = (line.credit_amount or Decimal("0")).quantize(self.QUANTIZE_TARGET, rounding=ROUND_HALF_UP)

        if debit > 0 and credit > 0:
            raise ValidationError("Journal line cannot have both debit and credit amounts.")
        if debit == 0 and credit == 0:
            raise ValidationError("Journal line must have either a debit or a credit amount.")

        line.debit_amount = debit
        line.credit_amount = credit
        line.functional_debit_amount = (debit * journal.exchange_rate).quantize(self.QUANTIZE_TARGET, rounding=ROUND_HALF_UP)
        line.functional_credit_amount = (credit * journal.exchange_rate).quantize(self.QUANTIZE_TARGET, rounding=ROUND_HALF_UP)
        line.updated_at = timezone.now()
        line.save(
            update_fields=[
                "debit_amount",
                "credit_amount",
                "functional_debit_amount",
                "functional_credit_amount",
                "updated_at",
            ]
        )

        return debit - credit

    def _apply_line_effects(
        self,
        line: JournalLine,
        journal: Journal,
        posting_time: timezone.datetime,
    ) -> None:
        delta = self._prepare_line_amounts(line, journal)

        account = ChartOfAccount.objects.select_for_update().get(pk=line.account_id)
        account.current_balance = (account.current_balance or Decimal("0")) + delta
        account.save(update_fields=["current_balance"])

        GeneralLedger.objects.create(
            organization_id=journal.organization,
            account=account,
            journal=journal,
            journal_line=line,
            period=journal.period,
            transaction_date=journal.journal_date,
            debit_amount=line.debit_amount,
            credit_amount=line.credit_amount,
            balance_after=account.current_balance,
            currency_code=journal.currency_code,
            exchange_rate=journal.exchange_rate,
            functional_debit_amount=line.functional_debit_amount,
            functional_credit_amount=line.functional_credit_amount,
            department=line.department,
            project=line.project,
            cost_center=line.cost_center,
            description=line.description,
            source_module="Accounting",
            source_reference=journal.journal_number,
            created_by=self.user if hasattr(GeneralLedger, "created_by") else None,
        )

    # ---------------------------------------------------------------------
    # Core posting operations
    # ---------------------------------------------------------------------
    @transaction.atomic
    def _post_internal(self, journal: Journal, enforce_permission: bool) -> Journal:
        journal = (
            Journal.objects.select_for_update()
            .select_related("journal_type", "period", "organization")
            .get(pk=journal.pk)
        )
        lines = list(
            journal.lines.select_related("account", "department", "project", "cost_center").order_by("line_number")
        )

        if enforce_permission:
            self._validate_status_transition(journal, "posted", enforce_permission=True)
        else:
            # Status still needs to be legal, but permission was checked earlier.
            self._validate_status_transition(journal, "posted", enforce_permission=False)

        if journal.status == "posted":
            raise ValidationError("Journal is already posted.")
        if journal.is_locked and journal.status != "posted":
            raise ValidationError(self.ERR_JOURNAL_LOCKED)
        if journal.period is None:
            raise ValidationError("Journal must be assigned to an accounting period.")
        if journal.period.status != "open":
            raise ValidationError(self.ERR_PERIOD_CLOSED)

        self.validate(journal, lines)

        number_set = False
        if not journal.journal_number:
            journal.journal_number = journal.journal_type.get_next_journal_number(period=journal.period)
            number_set = True

        posting_time = timezone.now()

        for line in lines:
            self._apply_line_effects(line, journal, posting_time)

        journal.update_totals()
        journal.status = "posted"
        journal.is_locked = True
        journal.posted_at = posting_time
        if hasattr(journal, "posted_by"):
            journal.posted_by = self.user
        journal.updated_by = self.user

        update_fields = [
            "status",
            "is_locked",
            "posted_at",
            "updated_by",
            "updated_at",
            "total_debit",
            "total_credit",
        ]
        if hasattr(journal, "posted_by"):
            update_fields.append("posted_by")
        if number_set:
            update_fields.append("journal_number")

        journal.save(update_fields=update_fields)

        log_audit_event(
            self.user,
            journal,
            "posted",
            details=f"Journal {journal.journal_number} posted.",
        )
        logger.info(
            "Journal %s posted successfully by user %s",
            journal.pk,
            getattr(self.user, "pk", None),
        )
        journal.refresh_from_db()
        return journal

    def post(self, journal: Journal) -> Journal:
        """Public entry point for posting a journal."""
        return self._post_internal(journal, enforce_permission=True)

    # ---------------------------------------------------------------------
    # Reversal
    # ---------------------------------------------------------------------
    @transaction.atomic
    def reverse(self, original_journal: Journal) -> Journal:
        original = (
            Journal.objects.select_for_update()
            .select_related("journal_type", "period", "organization")
            .get(pk=original_journal.pk)
        )

        self._validate_status_transition(original, "reversed", enforce_permission=True)
        if original.status != "posted":
            raise ValidationError(self.ERR_REVERSAL_NOT_ALLOWED)
        if original.reversal_entries.exists():
            raise ValidationError(self.ERR_REVERSAL_ALREADY_EXISTS)

        reversal = Journal.objects.create(
            organization=original.organization,
            journal_type=original.journal_type,
            period=original.period,
            journal_date=timezone.now().date(),
            reference=f"REV:{original.journal_number}",
            description=f"Reversal of {original.journal_number}: {original.description or ''}".strip(),
            currency_code=original.currency_code,
            exchange_rate=original.exchange_rate,
            status="draft",
            created_by=self.user,
            is_reversal=True,
            reversal_of=original,
        )

        for line in original.lines.order_by("line_number").select_related(
            "account", "department", "project", "cost_center"
        ):
            JournalLine.objects.create(
                journal=reversal,
                line_number=line.line_number,
                account=line.account,
                description=f"Reversal of line {line.line_number}: {line.description or ''}".strip(),
                debit_amount=line.credit_amount,
                credit_amount=line.debit_amount,
                department=line.department,
                project=line.project,
                cost_center=line.cost_center,
                tax_code=line.tax_code,
                tax_rate=line.tax_rate,
                tax_amount=line.tax_amount,
                memo=line.memo,
                created_by=self.user,
            )

        reversal.update_totals()
        reversal = self._post_internal(reversal, enforce_permission=False)

        original.status = "reversed"
        original.is_locked = True
        original.updated_by = self.user
        original.updated_at = timezone.now()
        original.save(update_fields=["status", "is_locked", "updated_by", "updated_at"])

        log_audit_event(
            self.user,
            original,
            "reversed",
            details=f"Journal {original.journal_number} reversed by {reversal.journal_number}.",
        )
        log_audit_event(
            self.user,
            reversal,
            "posted_as_reversal",
            details=f"Reversal journal {reversal.journal_number} created for {original.journal_number}.",
        )

        logger.info(
            "Journal %s reversed by %s using reversal journal %s",
            original.pk,
            getattr(self.user, "pk", None),
            reversal.pk,
        )
        return reversal

    # ---------------------------------------------------------------------
    # Period management
    # ---------------------------------------------------------------------
    @transaction.atomic
    def reopen_period(self, period: AccountingPeriod) -> AccountingPeriod:
        organization = period.fiscal_year.organization if getattr(period, "fiscal_year", None) else self.organization
        self._check_permission(("accounting", "accountingperiod", "reopen_period"), organization)

        if period.status != "closed":
            raise ValidationError(self.ERR_PERIOD_NOT_CLOSED)

        period.status = "open"
        period.closed_at = None
        period.closed_by = None
        period.updated_at = timezone.now()
        period.updated_by = self.user
        period.save(update_fields=["status", "closed_at", "closed_by", "updated_at", "updated_by"])

        log_audit_event(
            self.user,
            period,
            "reopened",
            details=f"Accounting period {period.name} reopened.",
        )
        logger.info(
            "Accounting period %s reopened by user %s",
            period.pk,
            getattr(self.user, "pk", None),
        )
        return period
