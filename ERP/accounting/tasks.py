"""Celery tasks for accounting domain workflows."""
from __future__ import annotations

import logging
from datetime import date, timedelta

from celery import shared_task
from django.db import transaction
from django.core.files.base import ContentFile
from django.utils import timezone

from accounting.ird_service import submit_invoice_to_ird
from accounting.models import IRDSubmissionTask, RecurringJournal
from accounting.services import process_receipt_with_ocr
from accounting.services.create_voucher import create_voucher
from accounting.utils.event_utils import emit_integration_event

logger = logging.getLogger(__name__)


@shared_task
def generate_recurring_journals() -> None:
    today = date.today()
    recurring_journals = RecurringJournal.objects.filter(is_active=True, start_date__lte=today)

    for rj in recurring_journals:
        if rj.end_date and rj.end_date < today:
            rj.is_active = False
            rj.save()
            continue

        if rj.last_run_date and rj.last_run_date.month == today.month and rj.last_run_date.year == today.year:
            continue

        journal = rj.journal
        header_data = {
            'journal_date': today,
            'reference': f'Recurring: {journal.reference}',
            'description': journal.description,
        }
        lines_data = [
            {
                'account': line.account.pk,
                'debit_amount': line.debit_amount,
                'credit_amount': line.credit_amount,
                'description': line.description,
            }
            for line in journal.journal_lines.all()
        ]

        create_voucher(
            user=journal.created_by,
            config_id=journal.journal_type.voucher_config.pk,
            header_data=header_data,
            lines_data=lines_data,
            status='draft',
        )

        rj.last_run_date = today
        rj.save()


def _backoff_seconds(attempts: int) -> int:
    base = max(attempts - 1, 0)
    return min(2 ** base * 60, 60 * 60)


@shared_task(bind=True, autoretry_for=(), max_retries=0)
def process_ird_submission(self, submission_id: int) -> dict:
    """Submit a queued sales invoice to the IRD gateway."""
    try:
        with transaction.atomic():
            submission = (
                IRDSubmissionTask.objects
                .select_for_update()
                .select_related('invoice', 'invoice__customer', 'organization')
                .get(pk=submission_id)
            )
            if submission.is_terminal:
                return {"status": submission.status}

            now = timezone.now()
            if submission.next_attempt_at and submission.next_attempt_at > now:
                countdown = int((submission.next_attempt_at - now).total_seconds())
                process_ird_submission.apply_async((submission.pk,), countdown=max(countdown, 30))
                return {"status": "rescheduled", "countdown": countdown}

            submission.status = IRDSubmissionTask.STATUS_PROCESSING
            submission.last_attempt_at = now
            submission.attempts += 1
            submission.celery_task_id = self.request.id
            submission.save(update_fields=[
                'status',
                'last_attempt_at',
                'attempts',
                'celery_task_id',
                'updated_at',
            ])
            invoice = submission.invoice
    except IRDSubmissionTask.DoesNotExist:
        logger.warning("ird_submission.missing", submission_id=submission_id)
        return {"status": "missing"}

    try:
        result = submit_invoice_to_ird(invoice)
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "ird_submission.failed",
            submission_id=submission.pk,
            invoice_id=invoice.pk,
        )
        with transaction.atomic():
            submission.refresh_from_db()
            hard_fail = submission.attempts >= submission.max_attempts
            submission.status = (
                IRDSubmissionTask.STATUS_FAILED if hard_fail else IRDSubmissionTask.STATUS_PENDING
            )
            submission.last_error = str(exc)
            if hard_fail:
                submission.next_attempt_at = None
            else:
                delay_seconds = _backoff_seconds(submission.attempts)
                submission.next_attempt_at = timezone.now() + timedelta(seconds=delay_seconds)
            submission.save(update_fields=[
                'status',
                'last_error',
                'next_attempt_at',
                'updated_at',
            ])

            if not hard_fail and submission.next_attempt_at:
                countdown = int((submission.next_attempt_at - timezone.now()).total_seconds())
                process_ird_submission.apply_async((submission.pk,), countdown=max(countdown, 30))

        return {"status": submission.status, "error": str(exc)}

    submission.status = IRDSubmissionTask.STATUS_SUCCEEDED
    submission.last_error = ''
    submission.next_attempt_at = None
    submission.metadata = {
        **(submission.metadata or {}),
        'signature': result.signature,
        'ack_id': result.ack_id,
        'response': result.response,
    }
    submission.save(update_fields=['status', 'last_error', 'next_attempt_at', 'metadata', 'updated_at'])

    emit_integration_event(
        "sales_invoice_submitted_to_ird",
        invoice,
        {
            "invoice_number": invoice.invoice_number,
            "ack_id": result.ack_id,
            "signature": result.signature,
        },
    )
    logger.info(
        "ird_submission.succeeded",
        submission_id=submission.pk,
        invoice_id=invoice.pk,
        ack_id=result.ack_id,
    )
    return {"status": "succeeded", "ack_id": result.ack_id}


def _run_receipt_ocr(file_bytes: bytes, filename: str | None = None) -> dict:
    """Shared helper to process OCR from raw bytes."""
    safe_file = ContentFile(file_bytes)
    safe_file.name = filename or "receipt_upload"
    return process_receipt_with_ocr(safe_file)


@shared_task(bind=True, autoretry_for=(), max_retries=0)
def analyze_document_ocr(self, file_bytes: bytes, filename: str | None = None) -> dict:
    """
    Generic OCR task for any module to extract receipt/invoice data.
    Accepts raw bytes to avoid persisting temp files.
    """
    try:
        data = _run_receipt_ocr(file_bytes, filename)
        return {"success": True, "extracted_data": data}
    except Exception as exc:  # noqa: BLE001
        logger.exception("document_ocr.task_failed", extra={"filename": filename})
        return {"success": False, "error": str(exc)}


@shared_task(bind=True, autoretry_for=(), max_retries=0)
def analyze_expense_receipt(self, file_bytes: bytes, filename: str | None = None) -> dict:
    """
    Lightweight Celery task to OCR an expense receipt and return structured data.
    The task accepts raw bytes to avoid storing temp files on disk.
    """
    return analyze_document_ocr(file_bytes, filename)
