from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from .models import Journal, JournalLine, JournalType, VoucherModeConfig,AuditLog

from .utils import get_current_user, get_client_ip, get_current_request

def log_change(instance, action):
    user = get_current_user()
    request = get_current_request()
    ip = get_client_ip(request) if request else None

    if user and user.is_authenticated:
        AuditLog.objects.create(
            user=user,
            action=action,
            content_type=ContentType.objects.get_for_model(instance),
            object_id=instance.pk,
            changes=instance.get_changes(),
            ip_address=ip
        )

@receiver(post_save, sender=Journal)
def log_journal_change(sender, instance, created, **kwargs):
    log_change(instance, 'create' if created else 'update')

@receiver(post_delete, sender=Journal)
def log_journal_delete(sender, instance, **kwargs):
    log_change(instance, 'delete')

@receiver(post_save, sender=JournalLine)
def log_journal_line_change(sender, instance, created, **kwargs):
    log_change(instance, 'create' if created else 'update')

@receiver(post_delete, sender=JournalLine)
def log_journal_line_delete(sender, instance, **kwargs):
    log_change(instance, 'delete')

@receiver(post_save, sender=JournalType)
def create_default_voucher_config(sender, instance, created, **kwargs):
    """Automatically create a VoucherModeConfig for new journal types."""
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