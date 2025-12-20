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
    """Seed voucher definitions for the organization when new journal types are added."""
    if not created:
        return
    try:
        from accounting.services.voucher_seeding import seed_voucher_configs
        seed_voucher_configs(instance.organization, reset=False)
    except Exception:
        pass
