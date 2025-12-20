from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from django.forms.models import model_to_dict
from datetime import date, datetime
from decimal import Decimal
from threading import local

from ..models import (
    Journal,
    JournalLine,
    JournalType,
    VoucherModeConfig,
    AuditLog,
    FiscalYear,
    AccountingPeriod,
    ChartOfAccount,
    GeneralLedger,
    SalesOrder,
    SalesOrderLine,
    SalesInvoice,
    SalesInvoiceLine,
    DeliveryNote,
    DeliveryNoteLine,
    BudgetLine,
)
from ..utils.request import get_current_user, get_client_ip, get_current_request

__all__ = [
    'create_default_voucher_config'
]

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

def _to_json_safe(value):
    """Recursively convert common Python/Django types to JSON-serializable forms."""
    if value is None:
        return None
    if isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        # Use float for readability; switch to str if exact precision is required for audit
        return float(value)
    if isinstance(value, dict):
        return {k: _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_json_safe(v) for v in value]
    # Fallback to string representation
    try:
        return str(value)
    except Exception:
        return "<unserializable>"


def log_change(instance, action, changes=None):
    """
    Generic function to log model changes to AuditLog with organization scoping.
    Automatically detects organization from instance or request context.
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
        # Build a safe changes payload
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
        log_change(instance, 'create', {'created': _to_json_safe(current_state)})
        return

    previous_state = _pop_old_state(sender, instance)
    changes = _calculate_changes(previous_state, current_state)
    if changes:
        log_change(instance, 'update', changes)


def _audit_post_delete(sender, instance, **kwargs):
    log_change(instance, 'delete', {'deleted': _to_json_safe(model_to_dict(instance))})


# Register audit signal handlers for audited models
AUDITED_MODELS = (
    Journal,
    JournalLine,
    FiscalYear,
    AccountingPeriod,
    ChartOfAccount,
    GeneralLedger,
    SalesOrder,
    SalesOrderLine,
    SalesInvoice,
    SalesInvoiceLine,
    DeliveryNote,
    DeliveryNoteLine,
    BudgetLine,
)

for audited_model in AUDITED_MODELS:
    pre_save.connect(_audit_pre_save, sender=audited_model, weak=False)
    post_save.connect(_audit_post_save, sender=audited_model, weak=False)
    post_delete.connect(_audit_post_delete, sender=audited_model, weak=False)


@receiver(post_save, sender=JournalType)
def create_default_voucher_config(sender, instance, created, **kwargs):
    """Seed voucher definitions for the organization when new journal types are added."""
    if not created:
        return
    try:
        from accounting.services.voucher_seeding import seed_voucher_configs
        seed_voucher_configs(instance.organization, reset=False)
    except Exception:
        pass
