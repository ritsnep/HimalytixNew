from datetime import date

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import AssetEvent, APPayment, PurchaseInvoice, SalesInvoice, ARReceipt
from .utils.event_utils import emit_integration_event


@receiver(post_save, sender=AssetEvent)
def asset_event_handler(sender, instance, created, **kwargs):
    if created and instance.event_type == 'disposal':
        emit_integration_event(
            'asset_disposed',
            instance.asset,
            {
                'asset_id': instance.asset.pk,
                'description': instance.description,
                'amount': str(instance.amount),
                'event_date': instance.event_date.isoformat(),
            },
        )
