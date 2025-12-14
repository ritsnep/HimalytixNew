import datetime
import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from django.contrib.contenttypes.models import ContentType
from django.forms.models import model_to_dict

from accounting.models import AuditLog
from accounting.utils.audit_integrity import compute_field_changes

logger = logging.getLogger(__name__)

def convert_dates_to_strings(obj):
    """Backward-compatible name: convert common types to JSON-safe values.

    - datetime/date -> ISO string
    - Decimal -> float (or str if float not desired)
    - dict/list/tuple/set -> recursively converted
    - Other non-serializable -> str(obj)
    """
    if isinstance(obj, dict):
        return {k: convert_dates_to_strings(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [convert_dates_to_strings(i) for i in obj]
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    # Primitive JSON-safe types pass through
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    # Fallback to string to avoid JSON errors
    try:
        return str(obj)
    except Exception:
        return "<unserializable>"

def get_changed_data(old_instance, new_data):
    """
    Compares an old model instance with new data and returns a dictionary
    of changed fields with their old and new values.
    """
    changes = {}
    old_data = model_to_dict(old_instance) if old_instance else {}

    for field_name, new_value in new_data.items():
        old_value = old_data.get(field_name)
        
        # Handle cases where values might be objects (e.g., ForeignKey instances)
        # Compare their primary keys if they are model instances
        if hasattr(old_value, 'pk') and hasattr(new_value, 'pk'):
            if old_value.pk != new_value.pk:
                changes[field_name] = {'old': str(old_value), 'new': str(new_value)}
        elif str(old_value) != str(new_value): # Simple string comparison for other types
            changes[field_name] = {'old': str(old_value), 'new': str(new_value)}
            
    return changes

def _resolve_audit_user(user, model_instance):
    if user:
        return user
    for attr in ("updated_by", "created_by", "user", "owner"):
        candidate = getattr(model_instance, attr, None)
        if candidate:
            return candidate
    return None


def _resolve_organization(model_instance, explicit_org=None):
    if explicit_org:
        return explicit_org
    for attr in ("organization", "org", "tenant", "company"):
        value = getattr(model_instance, attr, None)
        if value is not None:
            return value
    return None


def _normalize_snapshot(snapshot: Any) -> Optional[Dict[str, Any]]:
    if snapshot is None:
        return None
    if isinstance(snapshot, dict):
        return snapshot
    if hasattr(snapshot, "_meta"):
        return model_to_dict(snapshot)
    # Unsupported types fallback to string keyed dict
    return {"value": snapshot}


def log_audit_event(
    user,
    model_instance,
    action,
    changes: Optional[Dict[str, Any]] = None,
    details: Optional[str] = None,
    ip_address: Optional[str] = None,
    *,
    before_state: Optional[Dict[str, Any]] = None,
    after_state: Optional[Dict[str, Any]] = None,
    async_write: bool = False,
    organization=None,
):
    """
    Logs an audit event for a given model instance.

    Supports optional before/after snapshots and async persistence to
    satisfy SYSTEM.md requirements for deterministic, append-only audits.
    """
    resolved_user = _resolve_audit_user(user, model_instance)
    if not resolved_user:
        logger.warning(
            "Skipping audit log for %s (action=%s) because no user was provided.",
            model_instance,
            action,
        )
        return None

    object_id = getattr(model_instance, "pk", None)
    if object_id is None:
        logger.warning("Skipping audit log for %s because object_id is None.", model_instance)
        return None

    content_type = ContentType.objects.get_for_model(model_instance)
    org = _resolve_organization(model_instance, organization)

    if changes is None and (before_state is not None or after_state is not None):
        before_payload = _normalize_snapshot(before_state)
        after_payload = _normalize_snapshot(after_state)
        changes = compute_field_changes(before_payload, after_payload or {})

    cleaned_changes = convert_dates_to_strings(changes or {})

    if async_write:
        try:
            from accounting.tasks import log_audit_event_async

            log_audit_event_async.delay(
                resolved_user.pk,
                action,
                content_type.pk,
                object_id,
                changes=cleaned_changes,
                details=details,
                ip_address=ip_address,
                organization_id=getattr(org, "pk", None),
            )
        except Exception:
            logger.exception("Failed to enqueue async audit log; falling back to sync write.")
        else:
            logger.info(
                "audit.event.enqueued",
                extra={
                    "action": action,
                    "content_type": content_type.model,
                    "object_id": getattr(model_instance, "pk", None),
                    "organization_id": getattr(org, "pk", None),
                },
            )
            return None

    entry = AuditLog.objects.create(
        user=resolved_user,
        organization=org,
        content_type=content_type,
        object_id=object_id,
        action=action,
        changes=cleaned_changes,
        details=details,
        ip_address=ip_address,
    )
    logger.info(
        "audit.event.recorded",
        extra={
            "audit_id": entry.pk,
            "action": action,
            "content_type": content_type.model,
            "object_id": entry.object_id,
            "organization_id": getattr(org, "pk", None),
        },
    )
    return entry
