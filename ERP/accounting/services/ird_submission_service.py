from __future__ import annotations

import logging
from typing import Optional

from django.db import transaction
from django.utils import timezone

from accounting.models import IRDSubmissionTask, SalesInvoice
from accounting.tasks import process_ird_submission

logger = logging.getLogger(__name__)


class IRDSubmissionService:
    """Enqueue sales invoices for asynchronous IRD submission."""

    def __init__(self, user=None):
        self.user = user

    def enqueue_invoice(
        self,
        invoice: SalesInvoice,
        *,
        priority: str = IRDSubmissionTask.PRIORITY_NORMAL,
    ) -> IRDSubmissionTask:
        if invoice is None:
            raise ValueError("Invoice is required")

        existing: Optional[IRDSubmissionTask] = (
            invoice.ird_submission_tasks
            .filter(status__in=[IRDSubmissionTask.STATUS_PENDING, IRDSubmissionTask.STATUS_PROCESSING])
            .order_by('next_attempt_at')
            .first()
        )
        if existing:
            logger.info(
                "ird_submission.already_pending",
                invoice_id=invoice.pk,
                submission_id=existing.pk,
            )
            return existing

        with transaction.atomic():
            task = IRDSubmissionTask.objects.create(
                organization=invoice.organization,
                invoice=invoice,
                priority=priority,
                next_attempt_at=timezone.now(),
                created_by=self.user,
                updated_by=self.user,
            )

        process_ird_submission.delay(task.pk)
        logger.info(
            "ird_submission.queued",
            invoice_id=invoice.pk,
            submission_id=task.pk,
        )
        return task
