from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from django.forms.models import model_to_dict
from datetime import date, datetime
from decimal import Decimal
from ..models import Journal, JournalLine, JournalType, VoucherModeConfig, AuditLog
from ..utils.request import get_current_user, get_client_ip, get_current_request

__all__ = [
    'log_journal_change',
    'log_journal_delete',
    'log_journal_line_change',
    'log_journal_line_delete',
    'create_default_voucher_config'
]

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


def log_change(instance, action):
    """
    Generic function to log model changes to AuditLog
    """
    user = get_current_user()
    request = get_current_request()
    ip = get_client_ip(request) if request else None

    if user and user.is_authenticated:
        # Build a safe changes payload
        changes = {}
        try:
            if hasattr(instance, 'get_changes') and callable(getattr(instance, 'get_changes')):
                changes = instance.get_changes() or {}
            else:
                # Fallbacks when no change-tracking method exists
                if action == 'create':
                    changes = model_to_dict(instance)
                elif action == 'delete':
                    changes = {"deleted": True}
                else:
                    # For 'update' without diff support, snapshot current state
                    changes = model_to_dict(instance)
        except Exception:
            # Never fail request on audit issue
            changes = {"audit": "unavailable"}

        # Ensure JSON serializable payload
        changes = _to_json_safe(changes)

        AuditLog.objects.create(
            user=user,
            action=action,
            content_type=ContentType.objects.get_for_model(instance),
            object_id=instance.pk,
            changes=changes,
            ip_address=ip
        )

@receiver(post_save, sender=Journal)
def log_journal_change(sender, instance, created, **kwargs):
    """Log journal creation and updates"""
    log_change(instance, 'create' if created else 'update')

@receiver(post_delete, sender=Journal)
def log_journal_delete(sender, instance, **kwargs):
    """Log journal deletion"""
    log_change(instance, 'delete')

@receiver(post_save, sender=JournalLine)
def log_journal_line_change(sender, instance, created, **kwargs):
    """Log journal line creation and updates"""
    log_change(instance, 'create' if created else 'update')

@receiver(post_delete, sender=JournalLine)
def log_journal_line_delete(sender, instance, **kwargs):
    """Log journal line deletion"""
    log_change(instance, 'delete')

@receiver(post_save, sender=JournalType)
def create_default_voucher_config(sender, instance, created, **kwargs):
    """Automatically create a VoucherModeConfig for new journal types"""
    if not created:
        return

    VoucherModeConfig.objects.get_or_create(
        organization=instance.organization,
        journal_type=instance,
        is_default=True,
        defaults={
            "name": f"Default Config for {instance.name}",
            "layout_style": "standard",
            "show_account_balances": True,
            "show_tax_details": True,
            "show_dimensions": True,
            "allow_multiple_currencies": False,
            "require_line_description": True,
            "default_currency": getattr(instance.organization, "base_currency_code", "USD"),
        },
    )