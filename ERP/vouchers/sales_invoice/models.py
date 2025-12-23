"""
Draft models for HTMX Sales Invoice.

The HTMX Sales Invoice module manages invoice data in a draft state prior to
finalisation. This allows for incremental editing, recalculations and
session persistence without committing to the permanent `SalesInvoice`
models. Once a draft is complete the data can be used to create an
instance of the core `SalesInvoice` and its related lines and receipts.

These models mirror many of the fields present on the main `SalesInvoice`
model while extending support for UI requirements such as custom
discounts, rounding amounts, VAT applicability per line and extra text
fields. They also include convenience fields like `amount_in_words` and
`remaining_balance` computed by the service.

Note: Drafts are not intended to be posted directly to journals. They
exist solely as a staging area for UI interactions. Use
`ERP.vouchers.sales_invoice.services.SalesInvoiceDraftService` to
manipulate and recalc drafts.
"""

from __future__ import annotations

import uuid
from django.conf import settings
from django.db import models


class SalesInvoiceDraft(models.Model):
    """Represents a draft Sales Invoice being assembled via the HTMX UI."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Optionally tie drafts to a user; if null they are anonymous/session drafts
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sales_invoice_drafts",
    )

    # Voucher identity
    invoice_prefix = models.CharField(max_length=10, default="SB")
    invoice_no = models.PositiveIntegerField(null=True, blank=True)
    invoice_series_id = models.PositiveIntegerField(null=True, blank=True)
    fiscal_year = models.CharField(max_length=20, null=True, blank=True)
    ref_no = models.CharField(max_length=100, null=True, blank=True)

    # Dates
    date_bs = models.CharField(max_length=20, null=True, blank=True)
    date_ad = models.DateField(null=True, blank=True)
    due_days = models.PositiveIntegerField(default=30)
    due_date_ad = models.DateField(null=True, blank=True)

    # Buyer
    buyer_id = models.PositiveIntegerField(null=True, blank=True)
    buyer_snapshot = models.JSONField(null=True, blank=True)

    # Accounts
    sales_account_id = models.PositiveIntegerField(null=True, blank=True)
    payment_mode = models.CharField(max_length=20, default="Credit")
    order_ref_id = models.CharField(max_length=100, null=True, blank=True)
    agent_id = models.PositiveIntegerField(null=True, blank=True)
    agent_area_id = models.PositiveIntegerField(null=True, blank=True)

    # Terms and narration
    terms_id = models.PositiveIntegerField(null=True, blank=True)
    narration = models.TextField(null=True, blank=True)

    # Header level amounts
    header_discount_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    header_discount_type = models.CharField(max_length=4, default="amt")  # amt or pct
    rounding_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Computed totals
    sub_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    nonvat_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    nonvat_discount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_nonvat_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    vatable_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    vatable_discount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_vatable_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    taxable_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    vat_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    amount_in_words = models.CharField(max_length=512, default="Zero rupees only.")
    remaining_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        db_table = "sales_invoice_draft"
        verbose_name = "Sales Invoice Draft"
        verbose_name_plural = "Sales Invoice Drafts"

    def __str__(self) -> str:
        return f"Draft SI {self.invoice_prefix}{self.invoice_no or ''} ({self.pk})"


class SalesInvoiceDraftLine(models.Model):
    """A line item attached to a SalesInvoiceDraft."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    draft = models.ForeignKey(
        SalesInvoiceDraft,
        related_name="lines",
        on_delete=models.CASCADE,
    )
    # Sequence number (ordering)
    sn = models.PositiveIntegerField(default=1)
    # Item fields
    item_id = models.PositiveIntegerField(null=True, blank=True)
    hs_code = models.CharField(max_length=64, null=True, blank=True)
    description = models.CharField(max_length=256, null=True, blank=True)
    qty = models.DecimalField(max_digits=14, decimal_places=2, default=1)
    unit_id = models.CharField(max_length=32, default="Nos")
    godown_id = models.PositiveIntegerField(null=True, blank=True)
    rate = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    disc_type = models.CharField(max_length=4, default="none")  # none, pct, amt
    disc_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    vat_applicable = models.BooleanField(default=True)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=13)
    net_rate = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    line_taxable = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    line_vat = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        db_table = "sales_invoice_draft_line"
        verbose_name = "Sales Invoice Draft Line"
        verbose_name_plural = "Sales Invoice Draft Lines"
        ordering = ["sn", "id"]

    def __str__(self) -> str:
        return f"DraftLine {self.sn} of {self.draft_id}"


class SalesInvoiceDraftReceipt(models.Model):
    """Represents a receipt applied to a SalesInvoiceDraft."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    draft = models.ForeignKey(
        SalesInvoiceDraft,
        related_name="receipts",
        on_delete=models.CASCADE,
    )
    account_id = models.PositiveIntegerField(null=True, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    note = models.CharField(max_length=256, null=True, blank=True)

    class Meta:
        db_table = "sales_invoice_draft_receipt"
        verbose_name = "Sales Invoice Draft Receipt"
        verbose_name_plural = "Sales Invoice Draft Receipts"

    def __str__(self) -> str:
        return f"Receipt {self.id} for Draft {self.draft_id}"
