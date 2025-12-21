from django.contrib import admin

from voucher_config.models import FooterChargeSetup, InventoryLineConfig, VoucherConfigMaster


@admin.register(VoucherConfigMaster)
class VoucherConfigMasterAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "organization", "affects_gl", "affects_inventory", "is_active")
    list_filter = ("organization", "affects_gl", "affects_inventory", "is_active")
    search_fields = ("code", "label")


@admin.register(InventoryLineConfig)
class InventoryLineConfigAdmin(admin.ModelAdmin):
    list_display = ("voucher_config", "show_rate", "show_amount", "show_discount")
    list_filter = ("show_rate", "show_amount", "show_discount")


@admin.register(FooterChargeSetup)
class FooterChargeSetupAdmin(admin.ModelAdmin):
    list_display = ("voucher_config", "ledger", "calculation_type", "rate", "amount", "can_edit", "is_active")
    list_filter = ("calculation_type", "can_edit", "is_active")
