from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from usermanagement.models import CustomUser, Organization


def current_fiscal_year_code(today: Optional[timezone.datetime] = None) -> str:
    """Return a fiscal year code; falls back to settings or calendar year."""
    today = today or timezone.now().date()
    configured = getattr(settings, "BILLING_FISCAL_YEAR", None)
    if configured:
        return str(configured)
    return str(today.year)


def quantize_amount(value: Decimal) -> Decimal:
    """Consistent monetary rounding (2dp, half up) for VAT compliance."""
    return (value or Decimal("0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class InvoiceSeries(models.Model):
    tenant = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="invoice_series")
    fiscal_year = models.CharField(max_length=16)
    current_number = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("tenant", "fiscal_year")
        ordering = ["tenant", "-fiscal_year"]

    def __str__(self) -> str:
        return f"{self.tenant} - {self.fiscal_year} ({self.current_number})"


class InvoiceHeader(models.Model):
    SYNC_STATUS = [
        ("pending", "Pending"),
        ("synced", "Synced"),
        ("failed", "Failed"),
        ("canceled", "Canceled"),
    ]

    tenant = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="billing_invoices")
    series = models.ForeignKey(InvoiceSeries, on_delete=models.PROTECT, null=True, blank=True, related_name="invoices")
    invoice_number = models.CharField(max_length=32)
    fiscal_year = models.CharField(max_length=16, blank=True)
    invoice_date = models.DateField(default=timezone.now)
    customer_name = models.CharField(max_length=255)
    customer_pan = models.CharField(max_length=32)
    customer_vat = models.CharField(max_length=32, blank=True, null=True)
    billing_address = models.TextField(blank=True, default="")
    payment_method = models.CharField(max_length=64, default="cash")
    taxable_amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal("0"))
    vat_amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal("0"))
    total_amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal("0"))
    sync_status = models.CharField(max_length=16, choices=SYNC_STATUS, default="pending")
    canceled = models.BooleanField(default=False)
    canceled_reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("tenant", "invoice_number")
        ordering = ("-invoice_date", "-id")

    def __str__(self) -> str:
        return f"{self.invoice_number} - {self.customer_name}"

    def _compute_totals(self) -> None:
        # Aggregate from attached lines when possible
        if self.pk:
            aggregates = self.lines.aggregate(
                taxable=models.Sum("taxable_amount"),
                vat=models.Sum("vat_amount"),
                total=models.Sum("line_total"),
            )
            self.taxable_amount = quantize_amount(aggregates.get("taxable") or Decimal("0"))
            self.vat_amount = quantize_amount(aggregates.get("vat") or Decimal("0"))
            self.total_amount = quantize_amount(aggregates.get("total") or Decimal("0"))
        else:
            # For newly created objects, trust preset values; serializers set them.
            self.taxable_amount = quantize_amount(self.taxable_amount)
            self.vat_amount = quantize_amount(self.vat_amount)
            self.total_amount = quantize_amount(self.total_amount or (self.taxable_amount + self.vat_amount))

    def save(self, *args, **kwargs):
        if self.pk and not getattr(self, "_allow_update", False):
            raise ValidationError("InvoiceHeader is immutable; use credit/debit notes for changes.")

        if not self.fiscal_year:
            self.fiscal_year = current_fiscal_year_code(self.invoice_date)

        if not self.invoice_number:
            # Generate sequential invoice number per tenant/fiscal year
            with transaction.atomic():
                series, _ = (
                    InvoiceSeries.objects.select_for_update()
                    .get_or_create(tenant=self.tenant, fiscal_year=self.fiscal_year)
                )
                series.current_number += 1
                series.save(update_fields=["current_number", "updated_at"])
                self.series = series
                self.invoice_number = f"{self.fiscal_year}-{series.current_number:06d}"

        self._compute_totals()

        super().save(*args, **kwargs)
        # Reset flag so accidental reuse does not bypass immutability
        if getattr(self, "_allow_update", False):
            self._allow_update = False


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(InvoiceHeader, on_delete=models.CASCADE, related_name="lines")
    description = models.TextField()
    quantity = models.DecimalField(max_digits=19, decimal_places=4, default=Decimal("1"))
    unit_price = models.DecimalField(max_digits=19, decimal_places=4, default=Decimal("0"))
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("13.0"))
    taxable_amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal("0"))
    vat_amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal("0"))
    line_total = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal("0"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("invoice", "id")

    def __str__(self) -> str:
        return f"{self.invoice.invoice_number} - {self.description}"

    def save(self, *args, **kwargs):
        if self.pk and not getattr(self, "_allow_update", False):
            raise ValidationError("InvoiceLine is immutable; create a note instead of editing.")

        self.taxable_amount = quantize_amount((self.quantity or 0) * (self.unit_price or 0))
        vat_rate_decimal = (self.vat_rate or Decimal("0")) / Decimal("100")
        self.vat_amount = quantize_amount(self.taxable_amount * vat_rate_decimal)
        self.line_total = quantize_amount(self.taxable_amount + self.vat_amount)

        super().save(*args, **kwargs)
        if getattr(self, "_allow_update", False):
            self._allow_update = False


class CreditDebitNote(models.Model):
    NOTE_TYPES = [("credit", "Credit"), ("debit", "Debit")]

    invoice = models.ForeignKey(InvoiceHeader, on_delete=models.PROTECT, related_name="notes")
    note_type = models.CharField(max_length=6, choices=NOTE_TYPES)
    reason = models.TextField()
    amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal("0"))
    taxable_amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal("0"))
    vat_amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal("0"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.note_type.title()} note for {self.invoice.invoice_number}"


class InvoiceAuditLog(models.Model):
    ACTIONS = [
        ("create", "Create"),
        ("cancel", "Cancel"),
        ("print", "Print"),
        ("export", "Export"),
        ("sync", "Sync"),
        ("note", "Credit/Debit Note"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    invoice = models.ForeignKey(InvoiceHeader, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs")
    action = models.CharField(max_length=32, choices=ACTIONS)
    description = models.TextField(blank=True, default="")
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-timestamp",)

    def __str__(self) -> str:
        return f"{self.get_action_display()} - {self.invoice or 'N/A'}"
