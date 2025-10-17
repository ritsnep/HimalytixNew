from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import VoucherSchema
from .loader import invalidate_schema_cache

@receiver(post_save, sender=VoucherSchema)
def invalidate_schema_on_save(sender, instance, **kwargs):
    invalidate_schema_cache(instance.code) 