from decimal import Decimal

from django.contrib import admin
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import Coalesce
from mptt.admin import MPTTModelAdmin
from .models import (
    ProductCategory, Product, Warehouse, Location, Batch,
    InventoryItem, StockLedger, StockLedgerReport, StockSummary
)


class ReadOnlyAdminMixin:
    """Read-only admin helper to expose reporting views without edits."""

    def has_view_permission(self, request, obj=None):
        return request.user.has_module_perms(self.model._meta.app_label)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(ProductCategory)
class ProductCategoryAdmin(MPTTModelAdmin):
    list_display = ('organization', 'code', 'name', 'parent', 'is_active')
    search_fields = ('code', 'name')
    list_filter = ('organization', 'is_active')
    mptt_indent_field = "name"
    list_select_related = ('organization', 'parent')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'organization', 'code', 'name', 'category', 'uom', 'sale_price',
        'cost_price', 'is_inventory_item', 'created_at'
    )
    search_fields = ('code', 'name', 'description', 'barcode', 'sku')
    list_filter = ('organization', 'category', 'is_inventory_item', 'uom')
    raw_id_fields = ('income_account', 'expense_account', 'inventory_account')
    list_select_related = ('organization', 'category', 'uom')

@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ('organization', 'code', 'name', 'city', 'country_code', 'is_active')
    search_fields = ('code', 'name', 'city')
    list_filter = ('organization', 'is_active', 'country_code')
    raw_id_fields = ('inventory_account',)
    list_select_related = ('organization',)

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('warehouse', 'code', 'name', 'location_type', 'is_active')
    search_fields = ('code', 'name')
    list_filter = ('warehouse__organization', 'warehouse', 'location_type', 'is_active')
    list_select_related = ('warehouse',)

@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ('organization', 'product', 'batch_number', 'serial_number', 'manufacture_date', 'expiry_date')
    search_fields = ('batch_number', 'serial_number')
    list_filter = ('organization', 'product')
    list_select_related = ('organization', 'product')

@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = (
        'organization', 'product', 'warehouse', 'location', 'batch',
        'quantity_on_hand', 'unit_cost', 'total_value', 'updated_at'
    )
    search_fields = (
        'product__code', 'product__name', 'warehouse__code', 'warehouse__name',
        'location__code', 'batch__batch_number', 'batch__serial_number'
    )
    list_filter = ('organization', 'warehouse', 'product')
    readonly_fields = ('updated_at',)
    list_select_related = ('organization', 'product', 'warehouse', 'location', 'batch')

    @admin.display(description="Total Value")
    def total_value(self, obj):
        try:
            return obj.quantity_on_hand * obj.unit_cost
        except Exception:
            return None


class StockLedgerBaseAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        'organization', 'product', 'warehouse', 'location', 'batch',
        'txn_type', 'reference_id', 'txn_date', 'qty_in', 'qty_out', 'unit_cost'
    )
    search_fields = (
        'product__code', 'product__name', 'warehouse__code', 'warehouse__name',
        'location__code', 'batch__batch_number', 'batch__serial_number',
        'reference_id'
    )
    list_filter = ('organization', 'warehouse', 'product', 'txn_type', 'txn_date')
    actions = None
    readonly_fields = ('created_at',)
    ordering = ('-txn_date', '-id')
    date_hierarchy = 'txn_date'
    list_select_related = ('organization', 'product', 'warehouse', 'location', 'batch')


@admin.register(StockLedger)
class StockLedgerAdmin(StockLedgerBaseAdmin):
    """Core ledger admin kept for drill-down access."""


@admin.register(StockLedgerReport)
class StockLedgerReportAdmin(StockLedgerBaseAdmin):
    """Report-friendly alias to surface ledger data in admin."""


@admin.register(StockSummary)
class StockSummaryAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    change_list_template = "admin/Inventory/stocksummary/change_list.html"
    list_filter = ('organization', 'warehouse', 'product')
    search_fields = (
        'product__code', 'product__name', 'warehouse__code', 'warehouse__name',
    )
    list_select_related = ('organization', 'product', 'warehouse')
    actions = None
    ordering = ('product__code', 'warehouse__code')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('organization', 'product', 'warehouse')

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context=extra_context)
        if not hasattr(response, "context_data") or "cl" not in response.context_data:
            return response

        queryset = response.context_data["cl"].queryset
        value_expression = ExpressionWrapper(
            F('quantity_on_hand') * F('unit_cost'),
            output_field=DecimalField(max_digits=24, decimal_places=4),
        )
        aggregated = (
            queryset.values(
                'organization__id',
                'organization__name',
                'product__id',
                'product__code',
                'product__name',
                'warehouse__id',
                'warehouse__code',
                'warehouse__name',
            )
            .annotate(
                quantity_on_hand=Coalesce(Sum('quantity_on_hand'), Decimal('0')),
                total_value=Coalesce(Sum(value_expression), Decimal('0')),
            )
            .order_by('organization__name', 'product__code', 'warehouse__code')
        )

        summary_rows = []
        total_qty = Decimal('0')
        total_value = Decimal('0')
        for row in aggregated:
            qty = row.get('quantity_on_hand') or Decimal('0')
            value = row.get('total_value') or Decimal('0')
            unit_cost = value / qty if qty else Decimal('0')
            summary_rows.append(
                {
                    "organization": row.get('organization__name') or 'N/A',
                    "product": f"{row.get('product__code') or ''} {row.get('product__name') or ''}".strip() or 'Unknown product',
                    "warehouse": f"{row.get('warehouse__code') or ''} {row.get('warehouse__name') or ''}".strip() or 'Unknown warehouse',
                    "quantity_on_hand": qty,
                    "unit_cost": unit_cost,
                    "total_value": value,
                }
            )
            total_qty += qty
            total_value += value

        response.context_data.update(
            {
                "summary_rows": summary_rows,
                "summary_total_qty": total_qty,
                "summary_total_value": total_value,
                "title": "Stock Summary",
            }
        )
        return response
