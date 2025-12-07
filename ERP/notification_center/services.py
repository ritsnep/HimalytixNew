from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple

from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.core.mail import EmailMessage
from django.utils import timezone
from django.urls import reverse

from .models import (
    ApprovalRequest,
    InAppNotification,
    MessageTemplate,
    NotificationLog,
    NotificationRule,
)

logger = logging.getLogger(__name__)


def resolve_path(obj: Any, path: str) -> Any:
    """Walk dotted attributes safely to fetch nested data."""
    current = obj
    for attr in (path or "").split("."):
        if not attr:
            continue
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(attr)
            continue
        current = getattr(current, attr, None)
    return current


def build_context(instance: Any, extra_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    context = {"object": instance, "instance": instance}
    if extra_context:
        context.update(extra_context)
    return context


def get_rules_for_model(model: type) -> List[NotificationRule]:
    content_type = ContentType.objects.get_for_model(model)
    return list(
        NotificationRule.objects.filter(content_type=content_type, is_active=True)
        .select_related("template")
    )


def capture_initial_state(instance: Any, rules: Iterable[NotificationRule]) -> Dict[str, Any]:
    tracked_fields = {rule.status_field for rule in rules if rule.status_field}
    if not tracked_fields or not getattr(instance, "pk", None):
        return {}

    qs = instance.__class__.objects.filter(pk=instance.pk)
    try:
        snapshot = qs.only(*tracked_fields).first()
    except Exception:
        snapshot = qs.first()

    initial: Dict[str, Any] = {}
    if snapshot:
        for field in tracked_fields:
            if hasattr(snapshot, field):
                initial[field] = getattr(snapshot, field, None)
    return initial


def normalize_recipients(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, (list, tuple, set)):
        return [str(v).strip() for v in raw if str(v).strip()]
    if isinstance(raw, str):
        parts = [part.strip() for part in raw.split(",")]
        return [part for part in parts if part]
    return [str(raw).strip()]


def resolve_email(rule: NotificationRule, instance: Any) -> List[str]:
    target = None
    if rule.target_email_path:
        target = resolve_path(instance, rule.target_email_path)
    if not target and rule.direct_email:
        target = rule.direct_email
    if not target and rule.direct_user:
        target = getattr(rule.direct_user, "email", None)
    if not target and hasattr(instance, "user"):
        user = getattr(instance, "user", None)
        target = getattr(user, "email", None)
    if not target and hasattr(instance, "email"):
        target = getattr(instance, "email", None)
    return normalize_recipients(target)


def resolve_user(rule: NotificationRule, instance: Any, request: Any = None) -> Any:
    if rule.target_user_path:
        candidate = resolve_path(instance, rule.target_user_path)
        if candidate:
            return candidate
    if rule.direct_user:
        return rule.direct_user
    if hasattr(instance, "user"):
        return getattr(instance, "user")
    if hasattr(instance, "owner"):
        return getattr(instance, "owner")
    if rule.fallback_to_request_user and request is not None:
        if getattr(request, "user", None) and request.user.is_authenticated:
            return request.user
    return None


def resolve_phone(rule: NotificationRule, instance: Any) -> Optional[str]:
    phone = resolve_path(instance, rule.target_phone_path) if rule.target_phone_path else None
    if not phone and rule.direct_phone:
        phone = rule.direct_phone
    if phone:
        return str(phone)
    if hasattr(instance, "phone"):
        return str(getattr(instance, "phone"))
    return None


def dispatch_for_instance(
    instance: Any,
    created: bool = False,
    request: Any = None,
    extra_context: Optional[Dict[str, Any]] = None,
) -> List[NotificationLog]:
    rules = get_rules_for_model(instance.__class__)
    if not rules:
        return []

    initial_state = getattr(instance, "__notification_initial__", {}) or {}
    dispatched: List[NotificationLog] = []

    for rule in rules:
        try:
            if not rule.should_fire(instance, created, initial_state):
                continue
            dispatched.extend(
                _dispatch_rule(rule, instance, request=request, extra_context=extra_context)
            )
        except Exception:
            logger.exception("Failed to evaluate notification rule %s", rule.pk)
    return dispatched


def _dispatch_rule(
    rule: NotificationRule,
    instance: Any,
    request: Any = None,
    extra_context: Optional[Dict[str, Any]] = None,
) -> List[NotificationLog]:
    context = build_context(instance, extra_context)
    subject, body = rule.template.render(context)
    logs: List[NotificationLog] = []

    for channel in rule.resolved_channels():
        try:
            status, detail, recipient = _send_channel(
                channel=channel,
                rule=rule,
                instance=instance,
                subject=subject or rule.template.name,
                body=body,
                request=request,
            )
        except Exception as exc:  # Broad to ensure we log failure rather than crash
            logger.exception("Dispatch failed for rule %s on channel %s", rule.pk, channel)
            status = NotificationLog.Status.FAILED
            detail = str(exc)
            recipient = ""

        logs.append(
            NotificationLog.objects.create(
                rule=rule,
                template=rule.template,
                content_type=ContentType.objects.get_for_model(instance.__class__),
                object_id=str(getattr(instance, "pk", "")),
                channel=channel,
                status=status,
                recipient=recipient,
                rendered_subject=subject,
                rendered_body=body,
                detail=detail,
            )
        )

    if logs:
        rule.last_triggered_at = timezone.now()
        rule.save(update_fields=["last_triggered_at"])

    return logs


def dispatch_single_rule(
    rule: NotificationRule,
    instance: Any,
    request: Any = None,
    extra_context: Optional[Dict[str, Any]] = None,
) -> List[NotificationLog]:
    """
    Public helper to dispatch a specific rule (used by admin simulations).
    """
    return _dispatch_rule(rule, instance, request=request, extra_context=extra_context)


def create_approval_notification(
    *, instance: Any, requested_by: Any, approver: Any, title: str, message: str = "", metadata: Optional[Dict[str, Any]] = None
) -> ApprovalRequest:
    """Utility to persist an approval request and send an in-app notification with a link."""
    metadata = metadata or {}
    approval = ApprovalRequest.objects.create(
        title=title,
        message=message,
        content_type=ContentType.objects.get_for_model(instance.__class__),
        object_id=str(getattr(instance, "pk", "")),
        requested_by=requested_by,
        approver=approver,
        metadata=metadata,
    )
    InAppNotification.objects.create(
        recipient=approver,
        title=title,
        body=message or "An approval is pending your action.",
        content_type=approval.content_type,
        object_id=approval.id,
        action_url=reverse("notification_center:approval_detail", args=[approval.id]),
    )
    return approval


def _send_channel(
    channel: str,
    rule: NotificationRule,
    instance: Any,
    subject: str,
    body: str,
    request: Any = None,
) -> Tuple[str, str, str]:
    if channel == MessageTemplate.Channel.EMAIL:
        return _send_email(rule, instance, subject, body)
    if channel == MessageTemplate.Channel.IN_APP:
        return _send_in_app(rule, instance, subject, body, request=request)
    if channel == MessageTemplate.Channel.DJANGO_MESSAGE:
        return _send_django_message(subject, body, request)
    if channel == MessageTemplate.Channel.SMS:
        return _send_sms(rule, instance, body)
    return NotificationLog.Status.SKIPPED, f"Unknown channel {channel}", ""


def _send_email(
    rule: NotificationRule, instance: Any, subject: str, body: str
) -> Tuple[str, str, str]:
    recipients = resolve_email(rule, instance)
    if not recipients:
        return NotificationLog.Status.SKIPPED, "No email recipient resolved", ""

    message = EmailMessage(subject=subject or rule.template.name, body=body, to=recipients)
    if rule.template.is_html:
        message.content_subtype = "html"
    message.send(fail_silently=False)
    return NotificationLog.Status.SUCCESS, "Dispatched via email backend", ", ".join(recipients)


def _send_in_app(
    rule: NotificationRule, instance: Any, subject: str, body: str, request: Any = None
) -> Tuple[str, str, str]:
    user = resolve_user(rule, instance, request=request)
    if not user:
        return NotificationLog.Status.SKIPPED, "No user resolved for in-app notification", ""

    notification = InAppNotification.objects.create(
        recipient=user,
        title=subject or rule.template.name,
        body=body,
        content_type=ContentType.objects.get_for_model(instance.__class__),
        object_id=str(getattr(instance, "pk", "")),
    )
    return NotificationLog.Status.SUCCESS, "Stored in-app notification", str(user)


def _send_django_message(
    subject: str, body: str, request: Any = None
) -> Tuple[str, str, str]:
    if request is None:
        return NotificationLog.Status.SKIPPED, "Request not provided for Django messages", ""
    messages.add_message(
        request,
        messages.INFO,
        body or subject,
    )
    recipient = getattr(getattr(request, "user", None), "email", "") or str(
        getattr(request, "user", "")
    )
    return NotificationLog.Status.SUCCESS, "Added to Django messages framework", recipient


def _send_sms(rule: NotificationRule, instance: Any, body: str) -> Tuple[str, str, str]:
    phone = resolve_phone(rule, instance)
    if not phone:
        return NotificationLog.Status.SKIPPED, "No phone number resolved for SMS", ""
    # Placeholder SMS logic
    logger.info("SMS placeholder send to %s: %s", phone, body)
    return NotificationLog.Status.SUCCESS, "SMS placeholder executed", phone
