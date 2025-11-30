from django.contrib import admin

from .models import IRDSettings, Invoice, CreditNote, IRDLog


@admin.register(IRDSettings)
class IRDSettingsAdmin(admin.ModelAdmin):
    list_display = ("seller_pan", "username", "updated_at")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "invoice_date", "buyer_name", "status", "updated_at")
    list_filter = ("status", "invoice_date")
    search_fields = ("invoice_number", "buyer_name", "buyer_pan")


@admin.register(CreditNote)
class CreditNoteAdmin(admin.ModelAdmin):
    list_display = ("credit_note_number", "credit_note_date", "ref_invoice", "status", "updated_at")
    list_filter = ("status", "credit_note_date")
    search_fields = ("credit_note_number", "ref_invoice__invoice_number")


@admin.register(IRDLog)
class IRDLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "invoice", "credit_note", "success")
    list_filter = ("success",)
    search_fields = (
        "invoice__invoice_number",
        "credit_note__credit_note_number",
        "request_payload",
        "response_payload",
    )
