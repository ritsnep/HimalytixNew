from django.db import models
from django.conf import settings
from django.utils import timezone

class VoucherSchema(models.Model):
    code = models.CharField(max_length=64, unique=False, db_index=True, help_text="Voucher type code, e.g. PAYMENT")
    version = models.CharField(max_length=32, default="1.0", help_text="Schema version string or number")
    content = models.JSONField(help_text="Full UI schema as JSON")
    last_modified = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='created_voucher_schemas'
    )
    is_active = models.BooleanField(default=True, help_text="Is this schema active for this code?")
    source = models.CharField(max_length=16, default="db", help_text="db or file")
    git_sha = models.CharField(max_length=40, blank=True, null=True, help_text="Git SHA for auditability")

    class Meta:
        unique_together = ("code", "version")
        ordering = ["-last_modified"]
        indexes = [
            models.Index(fields=["code", "is_active"]),
        ]

    def __str__(self):
        return f"{self.code} v{self.version} ({'active' if self.is_active else 'inactive'})" 