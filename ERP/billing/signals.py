from __future__ import annotations

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import CreditDebitNote, InvoiceAuditLog, InvoiceHeader, InvoiceLine


def _actor(instance):
    return getattr(instance, "_actor", None)


@receiver(post_save, sender=InvoiceHeader)
def log_invoice_creation(sender, instance: InvoiceHeader, created, **kwargs):
    if created:
        InvoiceAuditLog.objects.create(
            user=_actor(instance),
            invoice=instance,
            action="create",
            description=f"Invoice {instance.invoice_number} created",
        )


@receiver(post_save, sender=CreditDebitNote)
def log_note(sender, instance: CreditDebitNote, created, **kwargs):
    if created:
        InvoiceAuditLog.objects.create(
            user=_actor(instance.invoice),
            invoice=instance.invoice,
            action="note",
            description=f"{instance.note_type.title()} note created: {instance.reason}",
        )


@receiver(post_delete, sender=InvoiceLine)
def log_line_delete(sender, instance: InvoiceLine, **kwargs):
    InvoiceAuditLog.objects.create(
        user=_actor(instance.invoice),
        invoice=instance.invoice,
        action="export",
        description=f"Line deleted from {instance.invoice.invoice_number}: {instance.description}",
    )
    if instance.invoice_id and InvoiceHeader.objects.filter(pk=instance.invoice_id).exists():
        instance.invoice.refresh_totals_from_lines()
