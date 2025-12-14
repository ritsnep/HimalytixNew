from django.contrib import admin

from .models import ConfigurationEntry, FeatureToggle


@admin.register(ConfigurationEntry)
class ConfigurationEntryAdmin(admin.ModelAdmin):
    list_display = ("key", "scope", "organization", "is_sensitive", "updated_at")
    list_filter = ("scope", "is_sensitive", "organization")
    search_fields = ("key", "description", "organization__name", "organization__code")
    readonly_fields = ("created_at", "updated_at")


@admin.register(FeatureToggle)
class FeatureToggleAdmin(admin.ModelAdmin):
    list_display = ("key", "module", "organization", "is_enabled", "starts_on", "expires_on")
    list_filter = ("module", "is_enabled", "organization")
    search_fields = ("key", "module", "organization__name", "organization__code")
    readonly_fields = ("updated_at",)
