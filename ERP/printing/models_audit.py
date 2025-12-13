"""Audit models for printing.

Kept separate from `models.py` to avoid making the core config model noisy.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class PrintSettingsAuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    organization_id = models.BigIntegerField(null=True, blank=True)
    action = models.CharField(max_length=64, default="settings_update")
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"], name="printing_audit_user_ts_idx"),
            models.Index(fields=["organization_id", "created_at"], name="printing_audit_org_ts_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} {self.action} {self.created_at:%Y-%m-%d %H:%M:%S}"
