from django.contrib import admin

from reporting.models import (
    ReportDefinition,
    ReportExecutionLog,
    ReportTemplate,
    ScheduledReport,
)


@admin.register(ReportDefinition)
class ReportDefinitionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "organization", "is_custom_enabled", "is_active", "updated_at")
    list_filter = ("is_active", "is_custom_enabled", "organization")
    search_fields = ("code", "name", "description", "query_name")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("organization_id", "code")


@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "definition", "organization", "is_default", "is_active", "version", "updated_at")
    list_filter = ("is_active", "is_default", "is_gallery", "organization")
    search_fields = ("name", "description", "definition__code", "definition__name")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("definition__code", "-is_default", "-version")


@admin.register(ScheduledReport)
class ScheduledReportAdmin(admin.ModelAdmin):
    list_display = ("report_code", "organization", "frequency", "format", "next_run", "is_active")
    list_filter = ("frequency", "format", "is_active", "organization")
    search_fields = ("report_code", "report_definition__name", "organization__name")
    readonly_fields = ("created_at", "updated_at", "last_run_at", "last_status")
    ordering = ("-next_run",)


@admin.register(ReportExecutionLog)
class ReportExecutionLogAdmin(admin.ModelAdmin):
    list_display = ("report_definition", "organization", "status", "run_at", "completed_at", "output_format")
    list_filter = ("status", "output_format", "organization")
    search_fields = ("report_definition__code", "message")
    readonly_fields = ("run_at", "completed_at")
    ordering = ("-run_at",)
