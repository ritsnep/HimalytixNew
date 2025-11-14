from __future__ import annotations

from typing import Any, Iterable

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from accounting.models import ApprovalStep, ApprovalTask, ApprovalWorkflow


class WorkflowService:
    """Handles creation and approvals for multi-step workflows."""

    def __init__(self, user):
        self.user = user

    def _get_amount(self, obj: Any) -> float:
        for attr in ('total', 'amount', 'invoice_total', 'sum'):
            if hasattr(obj, attr):
                try:
                    return float(getattr(obj, attr))
                except (TypeError, ValueError):
                    continue
        return 0.0

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
        return task

    @transaction.atomic
    def approve(self, task: ApprovalTask, user, approved: bool, notes: str = '') -> ApprovalTask:
        if task.status not in {'pending'}:
            raise ValueError("Only pending tasks can be processed.")
        steps: Iterable[ApprovalStep] = task.workflow.steps.order_by('sequence')
        step = next((s for s in steps if s.sequence == task.current_step), None)
        if not step:
            raise ValueError("Invalid workflow step.")
        obj_amount = self._get_amount(task.content_object)
        if obj_amount < float(step.min_amount):
            # skip requirement
            next_step = step.sequence + 1
        else:
            next_step = step.sequence + 1
        if not approved:
            task.status = 'rejected'
        else:
            if step == list(steps)[-1]:
                task.status = 'approved'
            else:
                task.current_step = next_step
        task.notes = notes
        task.save(update_fields=['status', 'current_step', 'notes', 'updated_at'])
        return task
