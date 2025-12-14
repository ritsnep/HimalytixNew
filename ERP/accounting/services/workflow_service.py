from __future__ import annotations

from typing import Any, Iterable, List, Optional

from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from accounting.models import ApprovalStep, ApprovalTask, ApprovalWorkflow
from accounting.utils.audit import log_audit_event
from .approval_policy import ApprovalPolicyService


class WorkflowService:
    """Handles creation and approvals for multi-step workflows."""

    def __init__(self, user):
        self.user = user
        self.organization = (
            getattr(user, "get_active_organization", lambda: getattr(user, "organization", None))()
            if user
            else None
        )

    def _get_amount(self, obj: Any) -> float:
        for attr in ('total', 'amount', 'invoice_total', 'sum', 'total_debit', 'total_credit'):
            if hasattr(obj, attr):
                try:
                    return float(getattr(obj, attr))
                except (TypeError, ValueError):
                    continue
        return 0.0

    def _resolve_workflow(self, *, area: str) -> Optional[ApprovalWorkflow]:
        if not self.organization:
            return None
        policy = ApprovalPolicyService(self.organization)
        return policy.get_default_workflow(area)

    @transaction.atomic
    def submit_with_policy(self, obj: Any, *, area: str, initiator) -> ApprovalTask:
        workflow = self._resolve_workflow(area=area)
        if not workflow:
            raise ValidationError(f"No approval workflow configured for area '{area}'.")
        return self.submit(obj, workflow, initiator)

    @transaction.atomic
    def submit(self, obj: Any, workflow: ApprovalWorkflow, initiator) -> ApprovalTask:
        task = ApprovalTask.objects.create(
            workflow=workflow,
            content_type=ContentType.objects.get_for_model(obj),
            object_id=obj.pk,
            current_step=1,
            status='pending',
            initiator=initiator,
        )
        log_audit_event(
            initiator,
            obj,
            'submitted_for_approval',
            details=f"Workflow {workflow.name} initiated.",
        )
        return task

    def _ensure_authorized(self, step: ApprovalStep, user):
        required_role = getattr(step, "role", "")
        if required_role and getattr(user, "role", None) != required_role:
            raise PermissionDenied("You are not authorized to approve this step.")

    def _next_required_index(self, steps: List[ApprovalStep], start_index: int, amount: float) -> int:
        idx = start_index
        while idx < len(steps) and amount < float(steps[idx].min_amount):
            idx += 1
        return idx

    @transaction.atomic
    def approve(self, task: ApprovalTask, user, approved: bool, notes: str = '') -> ApprovalTask:
        if task.status not in {'pending'}:
            raise ValueError("Only pending tasks can be processed.")
        steps: List[ApprovalStep] = list(task.workflow.steps.order_by('sequence'))
        step_index = next((idx for idx, s in enumerate(steps) if s.sequence == task.current_step), None)
        if step_index is None:
            raise ValueError("Invalid workflow step.")

        obj_amount = self._get_amount(task.content_object)
        # Skip steps that are not required for this amount.
        step_index = self._next_required_index(steps, step_index, obj_amount)
        if step_index >= len(steps):
            task.status = 'approved'
            task.notes = notes
            task.save(update_fields=['status', 'notes', 'updated_at'])
            log_audit_event(user, task.content_object, 'approval_skipped', details="Amount below threshold.")
            return task

        step = steps[step_index]
        if obj_amount < float(step.min_amount):
            # Shouldn't happen after skipping logic, but guard anyway.
            task.status = 'approved'
            task.notes = notes
            task.save(update_fields=['status', 'notes', 'updated_at'])
            return task

        self._ensure_authorized(step, user)

        next_step_sequence = steps[step_index + 1].sequence if step_index + 1 < len(steps) else None
        if not approved:
            task.status = 'rejected'
        else:
            if next_step_sequence is None:
                task.status = 'approved'
            else:
                task.current_step = next_step_sequence
        task.notes = notes
        task.save(update_fields=['status', 'current_step', 'notes', 'updated_at'])
        action = 'approved' if approved else 'rejected'
        log_audit_event(
            user,
            task.content_object,
            f'workflow_{action}',
            details=f"{user} {action} workflow {task.workflow.name}",
        )
        return task
