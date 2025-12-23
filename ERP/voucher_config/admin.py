from django.contrib import admin

from voucher_config.models import FooterChargeSetup, InventoryLineConfig, VoucherConfigMaster, VoucherUDFConfig


class InventoryLineConfigInline(admin.TabularInline):
    model = InventoryLineConfig
    extra = 0
    fields = ('show_rate', 'show_amount', 'show_discount', 'show_quantity', 'show_product', 'show_batch', 'show_expiry', 'decimal_precision', 'is_fixed_product', 'allow_batch_in_stock_journal')


class FooterChargeSetupInline(admin.TabularInline):
    model = FooterChargeSetup
    extra = 0
    fields = ('ledger', 'calculation_type', 'rate', 'amount', 'can_edit', 'is_active')


class VoucherUDFConfigInline(admin.TabularInline):
    model = VoucherUDFConfig
    extra = 0
    fields = ('field_name', 'display_name', 'field_type', 'scope', 'is_required', 'is_active')


# Temporarily comment out admin registration to fix check errors
# @admin.register(VoucherConfigMaster)
# class VoucherConfigMasterAdmin(admin.ModelAdmin):
#     list_display = ("code", "label", "organization", "affects_gl", "affects_inventory", "is_active")
#     list_filter = ("organization", "affects_gl", "affects_inventory", "is_active")
#     search_fields = ("code", "label")
#     inlines = [InventoryLineConfigInline, FooterChargeSetupInline, VoucherUDFConfigInline]


@admin.register(InventoryLineConfig)
class InventoryLineConfigAdmin(admin.ModelAdmin):
    list_display = ("voucher_config", "show_rate", "show_amount", "show_discount")
    list_filter = ("show_rate", "show_amount", "show_discount")


@admin.register(FooterChargeSetup)
class FooterChargeSetupAdmin(admin.ModelAdmin):
    list_display = ("voucher_config", "ledger", "calculation_type", "rate", "amount", "can_edit", "is_active")
    list_filter = ("calculation_type", "can_edit", "is_active")


@admin.register(VoucherUDFConfig)
class VoucherUDFConfigAdmin(admin.ModelAdmin):
    list_display = ("voucher_config", "field_name", "display_name", "field_type", "scope", "is_required", "is_active")
    list_filter = ("field_type", "scope", "is_required", "is_active")
