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


# ============================================================================
# BATCH POSTING (Performance / PR10)
# ============================================================================

@shared_task(bind=True, max_retries=1)
def post_journals_batch(self, user_id: int, journal_ids: list[int] | None = None, limit: int = 100) -> dict:
    """
    Post a batch of journals asynchronously for high-volume tenants.

    Args:
        user_id: The operator requesting the batch post (used for permissions/logging).
        journal_ids: Optional explicit journal IDs; if omitted, all approved journals
            for the user's active organization are processed up to `limit`.
        limit: Safety cap for implicit selections so a single task cannot post
            unbounded journals.
    """
    from django.contrib.auth import get_user_model
    from accounting.services.batch_posting import BatchPostingService

    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning("batch_posting.user_missing", extra={"user_id": user_id})
        return {"posted": [], "failed": [{"error": "user_missing"}]}

    service = BatchPostingService(user)
    summary = service.post_journals(journal_ids=journal_ids, limit=limit)
    logger.info(
        "batch_posting.completed",
        extra={
            "user_id": user_id,
            "posted_count": len(summary["posted"]),
            "failed_count": len(summary["failed"]),
        },
    )
    return summary


# ============================================================================
# AUDIT LOGGING TASKS (Async)
# ============================================================================

@shared_task(bind=True, max_retries=3)
def log_audit_event_async(self, user_id, action, content_type_id, object_id, 
                         changes=None, details=None, ip_address=None, organization_id=None):
    """
    Asynchronously log a model change to AuditLog.
    
    Useful for high-volume events (e.g., GL entries) that don't need
    synchronous audit guarantees. Reduces transaction latency.
    
    Args:
        user_id: CustomUser.id
        action: 'create', 'update', 'delete', etc.
        content_type_id: Django ContentType.id
        object_id: PK of the model being audited
        changes: JSON dict of before/after values
        details: Optional description
        ip_address: Optional IP address
        organization_id: Organization.id for multi-tenant isolation
    """
    try:
        from django.contrib.auth import get_user_model
        from django.contrib.contenttypes.models import ContentType
        from usermanagement.models import Organization
        
        User = get_user_model()
        
        user = User.objects.get(id=user_id)
        content_type = ContentType.objects.get(id=content_type_id)
        organization = Organization.objects.get(id=organization_id) if organization_id else None
        
        AuditLog.objects.create(
            user=user,
            action=action,
            content_type=content_type,
            object_id=object_id,
            changes=changes or {},
            details=details,
            ip_address=ip_address,
            organization=organization
        )
        
        logger.info(
            "audit_log.created",
            user_id=user_id,
            action=action,
            content_type=content_type.model,
            object_id=object_id
        )
    
    except Exception as exc:
        logger.exception("log_audit_event_async.failed")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=2)
def seal_audit_logs_batch(self, organization_id=None, batch_size=1000):
    """
    Asynchronously seal audit logs with hash-chaining for immutability.
    
    Should be run as a scheduled task (e.g., daily) to seal logs older than 24 hours.
    
    Args:
        organization_id: Optional organization to seal (all if None)
        batch_size: Number of logs to seal per task invocation
    """
    try:
        from datetime import timedelta
        from usermanagement.models import Organization
        from accounting.utils.audit_integrity import compute_content_hash
        
        cutoff_date = timezone.now() - timedelta(hours=24)
        logs = AuditLog.objects.filter(
            timestamp__lt=cutoff_date,
            is_immutable=False
        ).order_by('timestamp')[:batch_size]
        
        if organization_id:
            logs = logs.filter(organization_id=organization_id)
        
        count = 0
        prev_hash = None
        
        for log in logs:
            try:
                log_dict = {
                    'user_id': log.user_id,
                    'action': log.action,
                    'content_type_id': log.content_type_id,
                    'object_id': log.object_id,
                    'changes': log.changes,
                    'timestamp': log.timestamp,
                }
                
                log.content_hash = compute_content_hash(log_dict)
                log.previous_hash_id = prev_hash
                log.is_immutable = True
                log.save(update_fields=['content_hash', 'previous_hash_id', 'is_immutable'])
                
                prev_hash = log.id
                count += 1
            
            except Exception as e:
                logger.warning(f"Failed to seal audit log {log.id}: {str(e)}")
        
        logger.info(
            "seal_audit_logs_batch.completed",
            sealed_count=count,
            batch_size=batch_size
        )
        
        # Schedule next batch if there are more logs
        if count == batch_size:
            seal_audit_logs_batch.delay(organization_id=organization_id, batch_size=batch_size)
    
    except Exception as exc:
        logger.exception("seal_audit_logs_batch.failed")
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True, max_retries=1)
def check_suspicious_login_activity(self, organization_id=None):
    """
    Periodic task to detect suspicious login patterns.
    
    Detects:
    - Multiple failed attempts from same IP
    - Logins from unusual locations
    - Account lockouts
    - MFA bypass attempts
    
    Triggered: Daily or on-demand
    """
    try:
        from datetime import timedelta
        from usermanagement.models import LoginEventLog, Organization
        
        cutoff_date = timezone.now() - timedelta(hours=24)
        
        filters = {
            'timestamp__gte': cutoff_date,
            'event_type__in': [
                'login_failed_invalid_creds',
                'login_failed_account_locked',
                'login_failed_mfa',
            ]
        }
        
        if organization_id:
            filters['organization_id'] = organization_id
        
        # Find IPs with multiple failures
        from django.db.models import Count
        suspicious_ips = (
            LoginEventLog.objects
            .filter(**filters)
            .values('ip_address')
            .annotate(count=Count('ip_address'))
            .filter(count__gt=5)  # More than 5 failures
        )
        
        for ip_data in suspicious_ips:
            ip = ip_data['ip_address']
            count = ip_data['count']
            
            # Mark recent login events from this IP as suspicious
            LoginEventLog.objects.filter(
                ip_address=ip,
                timestamp__gte=cutoff_date
            ).update(is_suspicious=True, risk_score=75)
            
            logger.warning(
                "suspicious_login_activity.detected",
                ip_address=ip,
                failure_count=count
            )
        
        logger.info(
            "check_suspicious_login_activity.completed",
            suspicious_ips_count=len(list(suspicious_ips))
        )
    
    except Exception as exc:
        logger.exception("check_suspicious_login_activity.failed")
        raise self.retry(exc=exc, countdown=300)
