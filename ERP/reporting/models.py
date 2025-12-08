from __future__ import annotations

from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.db import models
from django.utils import timezone


class ReportDefinition(models.Model):
    """Configures how a report is generated and rendered."""

    ENGINE_CHOICES = [
        ("django", "Django Templates"),
        ("jinja", "Jinja2"),
    ]

    code = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    organization = models.ForeignKey(
        "usermanagement.Organization",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="reporting_definitions",
    )
    query_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Stored procedure or query identifier used to fetch data.",
    )
    base_template_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Fallback Django template path for the base layout.",
    )
    template_html = models.TextField(
        blank=True,
        help_text="Inline custom template HTML saved from the designer.",
    )
    template_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="Raw JSON from the drag-and-drop designer (for rebuild).",
    )
    engine = models.CharField(max_length=20, choices=ENGINE_CHOICES, default="django")
    is_custom_enabled = models.BooleanField(
        default=False,
        help_text="Per-report toggle to allow custom template rendering.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reporting_created_report_definitions",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reporting_updated_report_definitions",
    )

    class Meta:
        db_table = "reporting_report_definition"
        unique_together = ("organization", "code")
        ordering = ["organization_id", "code"]

    def __str__(self) -> str:
        scope = getattr(self.organization, "name", "Global") or "Global"
        return f"{self.code} ({scope})"

    def custom_allowed(self, global_toggle: bool) -> bool:
        """Return True when both global and per-report toggles allow custom layouts."""
        return bool(global_toggle and self.is_custom_enabled and self.is_active)

    def active_template(self, global_toggle: bool):
        """Return the template object or inline template that should render this report."""
        if self.custom_allowed(global_toggle):
            templates = self.templates.filter(is_active=True)
            if self.organization_id:
                templates = templates.filter(
                    models.Q(organization__isnull=True) | models.Q(organization=self.organization)
                )
            template = templates.order_by("-is_default", "-updated_at").first()
            if template:
                return template
            if self.template_html:
                return self
        return None


class ReportTemplate(models.Model):
    """Template gallery entries and saved versions for a report definition."""

    definition = models.ForeignKey(
        ReportDefinition,
        on_delete=models.CASCADE,
        related_name="templates",
    )
    organization = models.ForeignKey(
        "usermanagement.Organization",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="reporting_report_templates",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    template_html = models.TextField()
    template_json = models.JSONField(default=dict, blank=True)
    engine = models.CharField(
        max_length=20, choices=ReportDefinition.ENGINE_CHOICES, default="django"
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Marks the template as the default for this definition.",
    )
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    is_gallery = models.BooleanField(
        default=False,
        help_text="Indicates if this template is a pre-built gallery item.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reporting_created_report_templates",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reporting_updated_report_templates",
    )

    class Meta:
        db_table = "reporting_report_template"
        ordering = ["-is_default", "-updated_at", "name"]

    def __str__(self) -> str:
        scope = getattr(self.organization, "name", "Global") or "Global"
        return f"{self.name} ({scope})"


class ScheduledReport(models.Model):
    """Represents a scheduled delivery of a report to one or more recipients."""

    FREQUENCY_CHOICES = [
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("cron", "Custom cron"),
    ]
    FORMAT_CHOICES = [
        ("pdf", "PDF"),
        ("excel", "Excel"),
        ("csv", "CSV"),
        ("html", "HTML"),
    ]

    report_definition = models.ForeignKey(
        ReportDefinition,
        on_delete=models.CASCADE,
        related_name="schedules",
    )
    report_code = models.CharField(max_length=100)
    organization = models.ForeignKey(
        "usermanagement.Organization",
        on_delete=models.CASCADE,
        related_name="reporting_scheduled_reports",
    )
    parameters = models.JSONField(default=dict, blank=True)
    recipients = models.JSONField(
        default=list, help_text="List of email recipients for the report run."
    )
    format = models.CharField(max_length=10, choices=FORMAT_CHOICES, default="pdf")
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    cron = models.CharField(
        max_length=64,
        blank=True,
        help_text="Optional cron expression used when frequency is 'cron'.",
    )
    next_run = models.DateTimeField()
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_status = models.CharField(max_length=20, default="pending")
    is_active = models.BooleanField(default=True)
    send_copy_to_owner = models.BooleanField(
        default=True,
        help_text="Send a copy to the user who created the schedule.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reporting_created_scheduled_reports",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reporting_updated_scheduled_reports",
    )

    class Meta:
        db_table = "reporting_scheduled_report"
        ordering = ["-next_run"]
        indexes = [
            models.Index(fields=["organization", "report_code"]),
            models.Index(fields=["is_active", "next_run"]),
        ]

    def __str__(self) -> str:
        return f"{self.report_code} schedule for {self.organization}"

    def compute_next_run(self, from_time: Optional[timezone.datetime] = None) -> timezone.datetime:
        """Compute the next runtime based on frequency."""
        base = from_time or timezone.now()
        if self.frequency == "daily":
            return base + timedelta(days=1)
        if self.frequency == "weekly":
            return base + timedelta(weeks=1)
        if self.frequency == "monthly":
            return base + timedelta(days=30)
        if self.frequency == "quarterly":
            return base + timedelta(days=90)
        return base + timedelta(days=1)

    def mark_executed(self, status: str, run_time: Optional[timezone.datetime] = None) -> None:
        """Update bookkeeping after a run."""
        now = run_time or timezone.now()
        self.last_status = status
        self.last_run_at = now
        self.next_run = self.compute_next_run(now)
        self.save(update_fields=["last_status", "last_run_at", "next_run", "updated_at"])


class ReportExecutionLog(models.Model):
    """Tracks scheduled and ad-hoc report executions."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("success", "Success"),
        ("failed", "Failed"),
    ]

    scheduled_report = models.ForeignKey(
        ScheduledReport,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="executions",
    )
    report_definition = models.ForeignKey(
        ReportDefinition,
        on_delete=models.CASCADE,
        related_name="executions",
    )
    organization = models.ForeignKey(
        "usermanagement.Organization",
        on_delete=models.CASCADE,
        related_name="reporting_report_executions",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    run_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    output_format = models.CharField(max_length=10, blank=True)
    message = models.TextField(blank=True)
    attachment_name = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reporting_report_run_logs",
    )

    class Meta:
        db_table = "reporting_report_execution_log"
        ordering = ["-run_at"]
        indexes = [
            models.Index(fields=["organization", "report_definition"]),
            models.Index(fields=["status", "run_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.report_definition.code} at {self.run_at} ({self.status})"

    def mark_complete(self, status: str, message: str = "", attachment_name: str = "", duration_ms: Optional[int] = None) -> None:
        """Mark the execution record as finished."""
        self.status = status
        self.message = message
        self.attachment_name = attachment_name
        self.completed_at = timezone.now()
        self.duration_ms = duration_ms
        self.save(
            update_fields=[
                "status",
                "message",
                "attachment_name",
                "completed_at",
                "duration_ms",
                "run_at",
            ]
        )
