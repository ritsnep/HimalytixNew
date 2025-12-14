from django.conf import settings
from django.db import models
from django.utils import timezone

from usermanagement.models import Organization


class ConfigurationEntry(models.Model):
    """Key/value configuration scoped per organization or globally."""

    SCOPE_CORE = "core"
    SCOPE_FINANCE = "finance"
    SCOPE_PROCUREMENT = "procurement"
    SCOPE_SUPPLY_CHAIN = "supply_chain"
    SCOPE_CRM = "crm"
    SCOPE_HR = "hr"
    SCOPE_CHOICES = [
        (SCOPE_CORE, "Core Platform"),
        (SCOPE_FINANCE, "Finance"),
        (SCOPE_PROCUREMENT, "Procurement"),
        (SCOPE_SUPPLY_CHAIN, "Supply Chain"),
        (SCOPE_CRM, "CRM"),
        (SCOPE_HR, "HR"),
    ]

    entry_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="configuration_entries",
        null=True,
        blank=True,
        help_text="NULL represents a global configuration entry.",
    )
    scope = models.CharField(max_length=64, choices=SCOPE_CHOICES, default=SCOPE_CORE)
    key = models.CharField(max_length=128)
    value = models.JSONField(default=dict, blank=True)
    description = models.TextField(blank=True)
    is_sensitive = models.BooleanField(
        default=False, help_text="Hide value in UI/API responses when True."
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_configuration_entries",
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "configuration_entry"
        ordering = ("organization_id", "scope", "key")
        unique_together = ("organization", "scope", "key")
        indexes = [
            models.Index(fields=("organization", "scope", "key"), name="cfg_scope_idx"),
        ]

    def __str__(self):
        org_part = self.organization.code if self.organization else "global"
        return f"{org_part}:{self.scope}:{self.key}"


class FeatureToggle(models.Model):
    """Feature flag per org (or global)."""

    toggle_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="feature_toggles",
        help_text="NULL entries apply globally to all organizations.",
    )
    module = models.CharField(max_length=64)
    key = models.CharField(max_length=128)
    is_enabled = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    starts_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_feature_toggles",
    )

    class Meta:
        db_table = "feature_toggle"
        unique_together = ("organization", "module", "key")
        ordering = ("organization_id", "module", "key")
        indexes = [
            models.Index(fields=("organization", "module", "key"), name="feature_toggle_idx"),
        ]

    def __str__(self):
        org_part = self.organization.code if self.organization else "global"
        return f"{org_part}:{self.module}:{self.key}"

    def is_active(self, today=None):
        today = today or timezone.now().date()
        if self.starts_on and today < self.starts_on:
            return False
        if self.expires_on and today > self.expires_on:
            return False
        return self.is_enabled
