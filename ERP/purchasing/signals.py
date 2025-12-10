"""
Signal handlers for Purchase Order and Goods Receipt audit logging.
Ensures all purchasing transactions are tracked in the AuditLog.
"""

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from django.forms.models import model_to_dict
from datetime import date, datetime
from decimal import Decimal
from threading import local

from .models import (
    PurchaseOrder,
    PurchaseOrderLine,
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseInvoice,
    PurchaseInvoiceLine,
    LandedCostDocument,
    LandedCostLine,
    LandedCostAllocation,
)
from accounting.models import AuditLog
from accounting.utils.request import get_current_user, get_client_ip, get_current_request

_audit_state = local()


def _get_state_bucket():
    if not hasattr(_audit_state, 'data'):
        _audit_state.data = {}
    return _audit_state.data


def _state_key(sender, instance):
    return (sender, instance.pk)


def _capture_old_state(sender, instance):
    if not instance.pk:
        return
    try:
        old_instance = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    _get_state_bucket()[_state_key(sender, instance)] = model_to_dict(old_instance)


def _pop_old_state(sender, instance):
    return _get_state_bucket().pop(_state_key(sender, instance), None)


def _to_json_safe(value):
    """Recursively convert common Python/Django types to JSON-serializable forms."""
    if value is None:
        return None
    if isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {k: _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_json_safe(v) for v in value]
    try:
        return str(value)
    except Exception:
        return "<unserializable>"


def _calculate_changes(previous_state, current_state):
    if previous_state is None:
        return {field: {'old': None, 'new': _to_json_safe(value)} for field, value in current_state.items()}

    changes = {}
    for field, new_value in current_state.items():
        old_value = previous_state.get(field)
        old_serialized = _to_json_safe(old_value)
        new_serialized = _to_json_safe(new_value)
        if old_serialized != new_serialized:
            changes[field] = {'old': old_serialized, 'new': new_serialized}
    return changes


def log_purchase_change(instance, action, changes=None):
    """
    Generic function to log purchase model changes to AuditLog with organization scoping.
    """
    user = get_current_user()
    request = get_current_request()
    ip = get_client_ip(request) if request else None

    # Attempt to determine organization from instance
    organization = None
    if hasattr(instance, 'organization'):
        organization = instance.organization
    elif hasattr(instance, 'organization_id'):
        from usermanagement.models import Organization
        try:
            organization = Organization.objects.get(id=instance.organization_id)
        except:
            pass
    
    # Fallback to request context
    if not organization and request:
        organization = getattr(request, 'active_organization', None)
    
    if user and user.is_authenticated:
        payload = {}
        try:
            if changes is not None:
                payload = changes
            elif hasattr(instance, 'get_changes') and callable(getattr(instance, 'get_changes')):
                payload = instance.get_changes() or {}
            else:
                if action == 'create':
                    payload = {'created': model_to_dict(instance)}
                elif action == 'delete':
                    payload = {'deleted': True}
                else:
                    payload = model_to_dict(instance)
        except Exception:
            payload = {'audit': 'unavailable'}

        payload = _to_json_safe(payload)

        AuditLog.objects.create(
            user=user,
            action=action,
            organization=organization,
            content_type=ContentType.objects.get_for_model(instance),
            object_id=instance.pk,
            changes=payload,
            ip_address=ip
        )


def _audit_pre_save(sender, instance, **kwargs):
    _capture_old_state(sender, instance)


def _audit_post_save(sender, instance, created, **kwargs):
    current_state = model_to_dict(instance)
    if created:
        log_purchase_change(instance, 'create', {'created': _to_json_safe(current_state)})
        return

    previous_state = _pop_old_state(sender, instance)
    changes = _calculate_changes(previous_state, current_state)
    if changes:
        log_purchase_change(instance, 'update', changes)


def _audit_post_delete(sender, instance, **kwargs):
    log_purchase_change(instance, 'delete', {'deleted': _to_json_safe(model_to_dict(instance))})


# Register audit signal handlers for purchasing models
AUDITED_PURCHASE_MODELS = (
    PurchaseOrder,
    PurchaseOrderLine,
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseInvoice,
    PurchaseInvoiceLine,
    LandedCostDocument,
    LandedCostLine,
    LandedCostAllocation,
)

for audited_model in AUDITED_PURCHASE_MODELS:
    pre_save.connect(_audit_pre_save, sender=audited_model, weak=False)
    post_save.connect(_audit_post_save, sender=audited_model, weak=False)
    post_delete.connect(_audit_post_delete, sender=audited_model, weak=False)
