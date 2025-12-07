from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Iterable, Tuple

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.template import Context, Template
from django.utils import timezone


class MessageTemplate(models.Model):
    """Reusable content blocks for each channel."""

    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        IN_APP = "in_app", "In-App"
        DJANGO_MESSAGE = "django_message", "Django Message"
        SMS = "sms", "SMS (placeholder)"

    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    channel = models.CharField(
        max_length=32, choices=Channel.choices, default=Channel.EMAIL
    )
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField(
        help_text="Django template string. `object`/`instance` is the saved model."
    )
    is_html = models.BooleanField(default=True)
    sample_context = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name

    def render(self, context: Dict[str, Any]) -> Tuple[str, str]:
        """Render subject/body with the provided context."""
        ctx = Context(context or {})
        subject_tpl = Template(self.subject or "")
        body_tpl = Template(self.body or "")
        return subject_tpl.render(ctx).strip(), body_tpl.render(ctx).strip()


class NotificationRule(models.Model):
    """Admin-configurable hook that maps events to templates/channels."""

    class Trigger(models.TextChoices):
        CREATED = "created", "On Create"
        STATUS_CHANGE = "status_change", "On Status Change"
        ALWAYS = "always", "Any Save"

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="notification_rules",
    )
    template = models.ForeignKey(
        MessageTemplate, on_delete=models.PROTECT, related_name="rules"
    )
    trigger = models.CharField(
        max_length=32, choices=Trigger.choices, default=Trigger.STATUS_CHANGE
    )
    status_field = models.CharField(
        max_length=64,
        default="status",
        help_text="Field to inspect for status changes.",
    )
    from_status = models.CharField(
        max_length=64, blank=True, help_text="Optional previous status filter."
    )
    to_status = models.CharField(
        max_length=64,
        blank=True,
        help_text="Optional new status filter (leave blank to fire on any change).",
    )
    channels = models.JSONField(
        default=list,
        blank=True,
        help_text="Override template channel; leave empty to use template default.",
    )
    target_email_path = models.CharField(
        max_length=255,
        blank=True,
        help_text="Dotted path on instance to resolve an email (e.g. user.email).",
    )
    target_user_path = models.CharField(
        max_length=255,
        blank=True,
        help_text="Dotted path on instance to resolve a user (e.g. owner).",
    )
    direct_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_rules_as_recipient",
        help_text="Fallback user when path resolution fails.",
    )
    direct_email = models.EmailField(
        blank=True,
        help_text="Fallback email when path resolution fails (for email channel).",
    )
    direct_phone = models.CharField(
        max_length=50,
        blank=True,
        help_text="Fallback phone when path resolution fails (for SMS channel).",
    )
    fallback_to_request_user = models.BooleanField(
        default=True,
        help_text="Use request.user as last resort for in-app and Django messages.",
    )
    target_phone_path = models.CharField(
        max_length=255,
        blank=True,
        help_text="Dotted path on instance to resolve a phone number for SMS.",
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_notification_rules",
    )
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "name"]
        verbose_name = "Notification Rule"
        verbose_name_plural = "Notification Rules"

    def __str__(self) -> str:
        return self.name

    def resolved_channels(self) -> Iterable[str]:
        return self.channels or [self.template.channel]

    def should_fire(
        self, instance: models.Model, created: bool, initial_state: Dict[str, Any]
    ) -> bool:
        if not self.is_active:
            return False
        if self.trigger == self.Trigger.CREATED:
            return created
        if self.trigger == self.Trigger.ALWAYS:
            return True

        field_name = self.status_field or "status"
        old_value = initial_state.get(field_name)
        new_value = getattr(instance, field_name, None)

        # If created, treat old value as None but allow firing if explicitly configured
        if created:
            old_value = None

        if old_value == new_value:
            return False
        if self.from_status and str(old_value) != str(self.from_status):
            return False
        if self.to_status and str(new_value) != str(self.to_status):
            return False
        return True


class NotificationLog(models.Model):
    """Audit trail for fired notifications."""

    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    rule = models.ForeignKey(
        NotificationRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="logs",
    )
    template = models.ForeignKey(
        MessageTemplate, on_delete=models.SET_NULL, null=True, blank=True
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=255)
    content_object = GenericForeignKey("content_type", "object_id")
    channel = models.CharField(max_length=32, choices=MessageTemplate.Channel.choices)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.SUCCESS
    )
    recipient = models.CharField(max_length=255, blank=True)
    rendered_subject = models.TextField(blank=True)
    rendered_body = models.TextField(blank=True)
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.get_status_display()} via {self.channel}"


class InAppNotification(models.Model):
    """Persisted in-app notification for message feed or inbox."""

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="in_app_notifications",
    )
    title = models.CharField(max_length=255)
    body = models.TextField()
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True
    )
    object_id = models.CharField(max_length=255, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")
    action_url = models.URLField(blank=True, help_text="Optional link to act on this notification.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.title} -> {self.recipient}"

    def mark_read(self) -> None:
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])


class ApprovalRequest(models.Model):
    """Approval workflow request that requires user to visit and approve/reject."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    title = models.CharField(max_length=255)
    message = models.TextField(blank=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=255)
    content_object = GenericForeignKey("content_type", "object_id")
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approval_requests_made",
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approval_requests_assigned",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    metadata = models.JSONField(default=dict, blank=True)
    decision_notes = models.TextField(blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.title} ({self.get_status_display()})"

    @property
    def is_open(self) -> bool:
        return self.status == self.Status.PENDING

    def approve(self, notes: str = ""):
        self.status = self.Status.APPROVED
        self.decision_notes = notes
        self.decided_at = timezone.now()
        self.save(update_fields=["status", "decision_notes", "decided_at", "updated_at"])

    def reject(self, notes: str = ""):
        self.status = self.Status.REJECTED
        self.decision_notes = notes
        self.decided_at = timezone.now()
        self.save(update_fields=["status", "decision_notes", "decided_at", "updated_at"])


class Transaction(models.Model):
    """Working example model with a status that drives notifications."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="transactions",
    )
    reference = models.CharField(max_length=64, unique=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    status = models.CharField(
        max_length=24, choices=Status.choices, default=Status.PENDING
    )
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.reference} ({self.get_status_display()})"

    @property
    def status_badge(self) -> str:
        return self.get_status_display()
