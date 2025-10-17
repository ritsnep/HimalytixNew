from django.db import models
from django.conf import settings

# Import VoucherModeConfig from its location (assumed to be in accounting.models)
from accounting.models import VoucherModeConfig

class VoucherSchema(models.Model):
    voucher_mode_config = models.ForeignKey(VoucherModeConfig, on_delete=models.CASCADE, related_name='schemas')
    schema = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    version = models.PositiveIntegerField(default=1)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ('voucher_mode_config', 'version')
    
    def __str__(self):
        return f"Schema v{self.version} for {self.voucher_mode_config}"
