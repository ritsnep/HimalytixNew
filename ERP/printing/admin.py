from django.contrib import admin

from .models import PrintTemplateConfig


@admin.register(PrintTemplateConfig)
class PrintTemplateConfigAdmin(admin.ModelAdmin):
    list_display = ("user", "template_name")
    search_fields = ("user__username", "user__email")
