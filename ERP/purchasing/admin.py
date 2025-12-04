from django.contrib import admin, messages

from purchasing.models import (
    LandedCostDocument,
    LandedCostLine,
    PurchaseInvoice,
    PurchaseInvoiceLine,
    PurchaseOrder,
    PurchaseOrderLine,
    GoodsReceipt,
    GoodsReceiptLine,
)
from purchasing.services.procurement import apply_landed_cost_document, post_purchase_invoice


class PurchaseInvoiceLineInline(admin.TabularInline):
    model = PurchaseInvoiceLine
    extra = 2
    autocomplete_fields = ["product", "warehouse", "expense_account", "input_vat_account"]


@admin.register(PurchaseInvoice)
class PurchaseInvoiceAdmin(admin.ModelAdmin):
    date_hierarchy = "invoice_date"
    list_display = (
        "number",
        "organization",
        "invoice_date",
        "supplier",
        "currency",
        "total_amount",
        "status",
    )
    list_filter = ("organization", "status", "supplier", "invoice_date")
    search_fields = ("number", "supplier__display_name", "supplier__code")
    inlines = [PurchaseInvoiceLineInline]
    actions = ["post_selected"]

    def post_selected(self, request, queryset):
        ok = 0
        failed = 0
        for pi in queryset:
            try:
                post_purchase_invoice(pi)
                ok += 1
            except Exception as exc:  # noqa: BLE001 - admin should surface errors
                failed += 1
                self.message_user(
                    request,
                    f"Failed to post {pi}: {exc}",
                    level=messages.ERROR,
                )
        if ok:
            self.message_user(request, f"{ok} purchase invoice(s) posted.")
        if failed and not ok:
            self.message_user(request, f"{failed} purchase invoice(s) failed to post.", level=messages.ERROR)

    post_selected.short_description = "Post selected purchase invoices"


class LandedCostLineInline(admin.TabularInline):
    model = LandedCostLine
    extra = 1
    autocomplete_fields = ["gl_account"]


@admin.register(LandedCostDocument)
class LandedCostDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "purchase_invoice",
        "organization",
        "document_date",
        "basis",
        "is_applied",
        "applied_at",
    )
    list_filter = ("organization", "basis", "is_applied")
    search_fields = ("purchase_invoice__number",)
    inlines = [LandedCostLineInline]
    actions = ["apply_selected"]

    def apply_selected(self, request, queryset):
        ok = 0
        failed = 0
        for doc in queryset:
            try:
                apply_landed_cost_document(doc)
                ok += 1
            except Exception as exc:  # noqa: BLE001 - admin needs visibility
                failed += 1
                self.message_user(
                    request,
                    f"Failed to apply landed cost for {doc}: {exc}",
                    level=messages.ERROR,
                )
        if ok:
            self.message_user(request, f"Landed cost applied for {ok} document(s).")
        if failed and not ok:
            self.message_user(request, f"{failed} landed cost document(s) failed.", level=messages.ERROR)


# Purchase Order Admin
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

