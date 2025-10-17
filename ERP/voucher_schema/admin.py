from django.contrib import admin
from .models import VoucherSchema

@admin.register(VoucherSchema)
class VoucherSchemaAdmin(admin.ModelAdmin):
    list_display = ("code", "version", "is_active", "last_modified", "git_sha")
    search_fields = ("code", "version")
    list_filter = ("is_active", "code")
    ordering = ("-last_modified",) 