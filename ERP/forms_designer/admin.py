from django.contrib import admin
from .models import VoucherSchema

@admin.register(VoucherSchema)
class VoucherSchemaAdmin(admin.ModelAdmin):
    list_display = ('voucher_mode_config', 'version', 'created_by', 'created_at')
    list_filter = ('voucher_mode_config', 'created_by')
    search_fields = ('voucher_mode_config__name',)
    ordering = ('-created_at',)
