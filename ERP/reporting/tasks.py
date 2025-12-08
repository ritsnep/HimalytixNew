from __future__ import annotations

import logging
from typing import Iterable

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone

from reporting.models import ReportExecutionLog, ReportDefinition, ScheduledReport
from reporting.services import ReportDataService, ReportRenderer

logger = logging.getLogger(__name__)


def _resolve_recipients(recipients: Iterable[str], schedule: ScheduledReport) -> list[str]:
    emails = [addr for addr in recipients if addr]
    if schedule.send_copy_to_owner and schedule.created_by and schedule.created_by.email:
        emails.append(schedule.created_by.email)
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for addr in emails:
        if addr not in seen:
            seen.add(addr)
            unique.append(addr)
    return unique


@shared_task
def dispatch_due_reports() -> int:
    """Entry point: find due schedules and execute them."""
    now = timezone.now()
    due = (
        ScheduledReport.objects.filter(is_active=True, next_run__lte=now)
        .select_related("report_definition", "organization", "created_by")
        .order_by("next_run")
    )
    count = 0
    for schedule in due:
        try:
            run_scheduled_report(schedule.pk)
            count += 1
        except Exception:  # noqa: BLE001
            logger.exception("Failed to enqueue scheduled report %s", schedule.pk)
    return count


@shared_task
def run_scheduled_report(schedule_id: int) -> None:
    """Render and send a scheduled report."""
    try:
        schedule = ScheduledReport.objects.select_related(
            "report_definition", "organization", "created_by"
        ).get(pk=schedule_id)
    except ScheduledReport.DoesNotExist:
        logger.warning("Scheduled report %s not found.", schedule_id)
        return

    definition: ReportDefinition = schedule.report_definition
    organization = schedule.organization
    start_time = timezone.now()
    log = ReportExecutionLog.objects.create(
        scheduled_report=schedule,
        report_definition=definition,
        organization=organization,
        status="pending",
        created_by=schedule.created_by,
        output_format=schedule.format,
    )
    try:
        data_service = ReportDataService(organization, user=schedule.created_by)
        context = data_service.build_context(definition, schedule.parameters or {})
        renderer = ReportRenderer(settings.ENABLE_CUSTOM_REPORTS)
        buffer, filename, content_type = renderer.render_export(definition, context, schedule.format)

        recipients = _resolve_recipients(schedule.recipients or [], schedule)
        if not recipients:
            raise ValueError("No recipients configured for this schedule.")

        email = EmailMessage(
            subject=f"{definition.name} - {organization}",
            body="Attached is your scheduled report.",
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", getattr(settings, "EMAIL_HOST_USER", None)),
            to=recipients,
        )
        email.attach(filename, buffer.getvalue(), content_type)
        email.send(fail_silently=False)

        schedule.mark_executed("success", run_time=start_time)
        duration_ms = int((timezone.now() - start_time).total_seconds() * 1000)
        log.mark_complete("success", attachment_name=filename, duration_ms=duration_ms)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Scheduled report %s failed", schedule.pk)
        schedule.mark_executed("failed", run_time=start_time)
        duration_ms = int((timezone.now() - start_time).total_seconds() * 1000)
        log.mark_complete("failed", message=str(exc), duration_ms=duration_ms)
