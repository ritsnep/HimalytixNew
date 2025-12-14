from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounting.models import AuditLog, Journal
from configuration.models import ConfigurationEntry
from configuration.services import ConfigurationService


class LifecycleTransitionError(ValidationError):
    """Raised when a lifecycle transition is not permitted."""


DEFAULT_TRANSITIONS: Dict[str, List[str]] = {
    "draft": ["awaiting_approval", "posted"],
    "awaiting_approval": ["approved", "rejected"],
    "approved": ["posted"],
    "rejected": ["draft"],
    "posted": ["reversed"],
    "reversed": [],
}


DEFAULT_VALIDATION_RULES = {
    "require_reference": False,
    "require_balanced_totals": True,
    "period_must_be_open": True,
}


@dataclass
class ValidationResult:
    errors: List[str]

    @property
    def is_valid(self) -> bool:
        return not self.errors


class DocumentValidationEngine:
    """Runs validation rules configured per organization/document type."""

    def __init__(self, organization):
        self.organization = organization

    def _load_rules(self) -> Dict[str, bool]:
        return ConfigurationService.get_value(
            organization=self.organization,
            scope=ConfigurationEntry.SCOPE_FINANCE,
            key="journal_validation_rules",
            default=DEFAULT_VALIDATION_RULES,
        ) or DEFAULT_VALIDATION_RULES

    def validate(self, journal: Journal, stage: str) -> ValidationResult:
        rules = self._load_rules()
        errors: List[str] = []

        if rules.get("require_reference") and not journal.reference:
            errors.append("Reference is required.")

        if rules.get("require_balanced_totals") and journal.total_debit != journal.total_credit:
            errors.append("Journal must be balanced before it can be sent to approval or posting.")

        if rules.get("period_must_be_open"):
            period = getattr(journal, "period", None)
            if not period or period.status != "open":
                errors.append("Accounting period must be open.")

        # Stage specific requirements.
        if stage == "posted" and journal.lines.filter(is_archived=False).count() == 0:
            errors.append("At least one line is required to post a journal.")

        return ValidationResult(errors=errors)


class DocumentLifecycleService:
    """State machine for Journal lifecycle with audit logging + validation."""

    def __init__(self, *, journal: Journal, acting_user):
        self.journal = journal
        self.acting_user = acting_user
        self.organization = journal.organization
        self.validation_engine = DocumentValidationEngine(self.organization)

    def _load_transitions(self) -> Dict[str, List[str]]:
        configured = ConfigurationService.get_value(
            organization=self.organization,
            scope=ConfigurationEntry.SCOPE_FINANCE,
            key="journal_lifecycle_transitions",
            default=DEFAULT_TRANSITIONS,
        )
        return configured or DEFAULT_TRANSITIONS

    def _ensure_actor_can_mutate(self):
        org_id = getattr(self.acting_user, "organization_id", None)
        if org_id and org_id != self.organization_id:
            raise LifecycleTransitionError("User not permitted to mutate journals for this organization.")

    @property
    def organization_id(self):
        return getattr(self.organization, "pk", None)

    def transition(self, target_status: str, reason: Optional[str] = None):
        self._ensure_actor_can_mutate()
        transitions = self._load_transitions()
        current = self.journal.status

        if target_status == current:
            raise LifecycleTransitionError(f"Journal already in {target_status} status.")

        allowed = transitions.get(current, [])
        if target_status not in allowed:
            raise LifecycleTransitionError(f"Cannot transition from {current} to {target_status}.")

        validation_result = self.validation_engine.validate(self.journal, target_status)
        if not validation_result.is_valid:
            raise ValidationError(validation_result.errors)

        with transaction.atomic():
            self._apply_status_change(target_status, reason)
            self.journal.save(update_fields=self._fields_for_status(target_status))
            self._write_audit_log(target_status, reason, validation_result.errors)

        return self.journal

    def _fields_for_status(self, status: str) -> List[str]:
        base_fields = ["status", "updated_at"]
        if status == "awaiting_approval":
            return base_fields
        if status == "approved":
            return base_fields + ["approved_at", "approved_by"]
        if status == "posted":
            return base_fields + ["posted_at", "posted_by", "is_locked"]
        if status == "reversed":
            return base_fields + ["is_locked", "metadata"]
        if status == "rejected":
            return base_fields + ["metadata"]
        return ["status"]

    def _apply_status_change(self, status: str, reason: Optional[str]):
        if not isinstance(self.journal.metadata, dict):
            self.journal.metadata = {}
        self.journal.status = status
        if status == "awaiting_approval":
            self.journal.is_locked = False
        elif status == "approved":
            self.journal.approved_by = self.acting_user
            self.journal.approved_at = timezone.now()
        elif status == "posted":
            self.journal.posted_by = self.acting_user
            self.journal.posted_at = timezone.now()
            self.journal.is_locked = True
        elif status == "reversed":
            self.journal.is_locked = True
            self.journal.metadata["reversal_reason"] = reason or ""
        elif status == "rejected":
            self.journal.metadata["rejection_reason"] = reason or ""

    def _write_audit_log(self, status: str, reason: Optional[str], errors: List[str]):
        AuditLog.objects.create(
            user=self.acting_user,
            organization=self.organization,
            action="update",
            content_type=ContentType.objects.get_for_model(Journal),
            object_id=self.journal.pk,
            changes={
                "status": status,
                "reason": reason,
                "validation_errors": errors,
            },
            details=f"Journal transition to {status}",
            ip_address=None,
        )
