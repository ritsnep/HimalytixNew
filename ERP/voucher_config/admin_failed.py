from django.contrib import admin
from .models import VoucherConfigMaster, VoucherUDFConfig


class FailedPostingAdmin(admin.ModelAdmin):
    list_display = ('voucher', 'current_step', 'error_code', 'created_at')
    list_filter = ('current_step', 'error_code')

# Register in admin.py
admin.site.register(FailedPostingAdmin)