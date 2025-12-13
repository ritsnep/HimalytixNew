from django.contrib import admin

from .models import PrintTemplate, PrintTemplateConfig
from .models_audit import PrintSettingsAuditLog


@admin.register(PrintTemplateConfig)
class PrintTemplateConfigAdmin(admin.ModelAdmin):
    list_display = ("user", "template_name")
    search_fields = ("user__username", "user__email")


@admin.register(PrintTemplate)
class PrintTemplateAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "document_type", "name", "paper_size")
    list_filter = ("document_type", "paper_size")
    search_fields = ("user__username", "user__email", "name")


@admin.register(PrintSettingsAuditLog)
class PrintSettingsAuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "organization_id", "action")
    list_filter = ("action",)
    search_fields = ("user__username", "user__email", "organization_id")
    readonly_fields = ("created_at",)
