from django.contrib import admin, messages

# ============================================================================
# CONSOLIDATED MODELS - Admin moved to accounting.admin
# ============================================================================
# PurchaseInvoice, LandedCost* models are now managed in accounting.admin
# Only import here for reference if needed by other admin classes
from accounting.models import (
    PurchaseInvoice,
    PurchaseInvoiceLine,
    LandedCostDocument,
    LandedCostLine,
)

# Import purchasing-specific models
from purchasing.models import (
    PurchaseOrder,
    PurchaseOrderLine,
    GoodsReceipt,
    GoodsReceiptLine,
)
from purchasing.services.procurement import post_purchase_invoice


# ============================================================================
# PURCHASING-SPECIFIC ADMIN (PurchaseOrder, GoodsReceipt)
# ============================================================================
# Note: PurchaseInvoice and LandedCost admin are in accounting.admin

# Removed PurchaseInvoice admin - now in accounting.admin
# Removed LandedCost admin - now in accounting.admin


# ============================================================================
# PURCHASE ORDER ADMIN
# ============================================================================

class PurchaseOrderLineInline(admin.TabularInline):
    model = PurchaseOrderLine
    extra = 1
    autocomplete_fields = ["product", "inventory_account", "expense_account"]


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    date_hierarchy = "order_date"
    list_display = (
        "number",
        "organization",
        "vendor",
        "order_date",
        "currency",
        "total_amount",
        "status",
    )
    list_filter = ("organization", "status", "vendor", "order_date")
    search_fields = ("number", "vendor__display_name", "vendor__code")
    readonly_fields = ("number", "subtotal", "tax_amount", "total_amount", "created_by", "created_at", "updated_at")
    inlines = [PurchaseOrderLineInline]
    fieldsets = (
        ("PO Information", {
            "fields": ("organization", "number", "vendor", "order_date", "due_date", "currency", "exchange_rate")
        }),
        ("Totals", {
            "fields": ("subtotal", "tax_amount", "total_amount"),
            "classes": ("collapse",)
        }),
        ("Status & Tracking", {
            "fields": ("status", "send_date", "expected_receipt_date"),
        }),
        ("Notes & Audit", {
            "fields": ("notes", "created_by", "created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )


# Goods Receipt Admin
class GoodsReceiptLineInline(admin.TabularInline):
    model = GoodsReceiptLine
    extra = 0
    readonly_fields = ("po_line", "created_at")


@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(admin.ModelAdmin):
    date_hierarchy = "receipt_date"
    list_display = (
        "number",
        "organization",
        "purchase_order",
        "warehouse",
        "receipt_date",
        "status",
    )
    list_filter = ("organization", "status", "warehouse", "receipt_date")
    search_fields = ("number", "purchase_order__number", "reference_number")
    readonly_fields = ("number", "journal", "created_by", "created_at", "updated_at", "posted_at")
    inlines = [GoodsReceiptLineInline]
    fieldsets = (
        ("GR Information", {
            "fields": ("organization", "number", "purchase_order", "warehouse", "receipt_date", "reference_number")
        }),
        ("Status & Posting", {
            "fields": ("status", "journal", "posted_at"),
        }),
        ("Quality Control", {
            "fields": ("notes",),
            "classes": ("collapse",)
        }),
        ("Audit", {
            "fields": ("created_by", "created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

