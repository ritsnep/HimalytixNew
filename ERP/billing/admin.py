from django.contrib import admin

from .models import CreditDebitNote, InvoiceAuditLog, InvoiceHeader, InvoiceLine, InvoiceSeries


@admin.register(InvoiceSeries)
class InvoiceSeriesAdmin(admin.ModelAdmin):
    list_display = ("tenant", "fiscal_year", "current_number", "updated_at")
    search_fields = ("tenant__name", "fiscal_year")


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0
    readonly_fields = ("description", "quantity", "unit_price", "vat_rate", "taxable_amount", "vat_amount", "line_total")


@admin.register(InvoiceHeader)
class InvoiceHeaderAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "tenant", "invoice_date", "customer_name", "total_amount", "sync_status", "canceled")
    readonly_fields = (
        "invoice_number",
        "taxable_amount",
        "vat_amount",
        "total_amount",
        "created_at",
        "updated_at",
    )
    inlines = [InvoiceLineInline]


@admin.register(CreditDebitNote)
class CreditDebitNoteAdmin(admin.ModelAdmin):
    list_display = ("invoice", "note_type", "amount", "created_at")


@admin.register(InvoiceAuditLog)
class InvoiceAuditLogAdmin(admin.ModelAdmin):
    list_display = ("invoice", "user", "action", "timestamp")
    readonly_fields = ("invoice", "user", "action", "description", "timestamp")
