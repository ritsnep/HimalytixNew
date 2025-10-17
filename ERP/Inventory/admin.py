from django.contrib import admin
from mptt.admin import MPTTModelAdmin
from .models import (
    ProductCategory, Product, Warehouse, Location, Batch,
    InventoryItem, StockLedger
)

@admin.register(ProductCategory)
class ProductCategoryAdmin(MPTTModelAdmin):
    list_display = ('organization', 'code', 'name', 'parent', 'is_active')
    search_fields = ('code', 'name')
    list_filter = ('organization', 'is_active')
    mptt_indent_field = "name"

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'organization', 'code', 'name', 'category', 'uom', 'sale_price',
        'cost_price', 'is_inventory_item', 'created_at'
    )
    search_fields = ('code', 'name', 'description', 'barcode', 'sku')
    list_filter = ('organization', 'category', 'is_inventory_item', 'uom')
    raw_id_fields = ('income_account', 'expense_account', 'inventory_account')

@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ('organization', 'code', 'name', 'city', 'country_code', 'is_active')
    search_fields = ('code', 'name', 'city')
    list_filter = ('organization', 'is_active', 'country_code')
    raw_id_fields = ('inventory_account',)

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('warehouse', 'code', 'name', 'location_type', 'is_active')
    search_fields = ('code', 'name')
    list_filter = ('warehouse__organization', 'warehouse', 'location_type', 'is_active')

@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ('organization', 'product', 'batch_number', 'serial_number', 'manufacture_date', 'expiry_date')
    search_fields = ('batch_number', 'serial_number')
    list_filter = ('organization', 'product')

@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = (
        'organization', 'product', 'warehouse', 'location', 'batch',
        'quantity_on_hand', 'unit_cost', 'updated_at'
    )
    search_fields = (
        'product__code', 'product__name', 'warehouse__code', 'warehouse__name',
        'location__code', 'batch__batch_number', 'batch__serial_number'
    )
    list_filter = ('organization', 'warehouse', 'product')
    readonly_fields = ('updated_at',)

@admin.register(StockLedger)
class StockLedgerAdmin(admin.ModelAdmin):
    list_display = (
        'organization', 'product', 'warehouse', 'location', 'batch',
        'txn_type', 'reference_id', 'txn_date', 'qty_in', 'qty_out', 'unit_cost'
    )
    search_fields = (
        'product__code', 'product__name', 'warehouse__code', 'warehouse__name',
        'location__code', 'batch__batch_number', 'batch__serial_number',
        'reference_id'
    )
    list_filter = ('organization', 'warehouse', 'product', 'txn_type')
    readonly_fields = ('created_at',)
    date_hierarchy = 'txn_date'
