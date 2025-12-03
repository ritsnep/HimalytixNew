from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.utils.translation import gettext_lazy as _

from inventory.models import Product, Warehouse
from accounting.models import ChartOfAccount, Currency, Vendor
from usermanagement.models import Organization


class PurchaseInvoice(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", _("Draft")
        POSTED = "posted", _("Posted")

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="purchasing_purchase_invoices",
    )
    supplier = models.ForeignKey(
        Vendor,
        on_delete=models.PROTECT,
        related_name="purchasing_purchase_invoices",
    )
    number = models.CharField(max_length=64)
    invoice_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)

    currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
    exchange_rate = models.DecimalField(max_digits=18, decimal_places=6, default=Decimal("1"))

    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    base_total_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)

    journal = models.OneToOneField(
        "accounting.Journal",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="purchase_invoice",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("organization", "number")
        ordering = ("-invoice_date", "-id")

    def __str__(self) -> str:
        return f"PI-{self.number}"

    def recalc_totals(self):
        """Recompute subtotal/tax/total from the invoice lines."""
        subtotal = Decimal("0")
        tax = Decimal("0")
        for line in self.lines.all():
            line_total = line.quantity * line.unit_price
            subtotal += line_total
            tax += line_total * (line.vat_rate / Decimal("100"))
        self.subtotal = subtotal.quantize(Decimal("0.01"))
        self.tax_amount = tax.quantize(Decimal("0.01"))
        self.total_amount = (self.subtotal + self.tax_amount).quantize(Decimal("0.01"))
        self.base_total_amount = (self.total_amount * self.exchange_rate).quantize(Decimal("0.01"))

    def save(self, *args, **kwargs):
        skip_recalc = kwargs.pop("skip_recalc", False)
        if self.pk and not skip_recalc:
            self.recalc_totals()
        super().save(*args, **kwargs)


class PurchaseInvoiceLine(models.Model):
    invoice = models.ForeignKey(
        PurchaseInvoice,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="purchase_lines",
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="purchase_lines",
    )
    description = models.CharField(max_length=255, blank=True)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit_price = models.DecimalField(max_digits=18, decimal_places=4)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0"))

    expense_account = models.ForeignKey(
        ChartOfAccount,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="purchase_expense_lines",
        help_text="Used for non-inventory items",
    )
    input_vat_account = models.ForeignKey(
        ChartOfAccount,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="purchase_vat_lines",
        help_text="Override VAT account for this line",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.product} x {self.quantity} @ {self.unit_price}"

    @property
    def line_subtotal(self) -> Decimal:
        return (self.quantity * self.unit_price).quantize(Decimal("0.01"))

    @property
    def line_tax_amount(self) -> Decimal:
        return (self.line_subtotal * (self.vat_rate / Decimal("100"))).quantize(Decimal("0.01"))

    @property
    def line_total(self) -> Decimal:
        return self.line_subtotal + self.line_tax_amount


class LandedCostBasis(models.TextChoices):
    BY_VALUE = "value", _("By line value")
    BY_QUANTITY = "quantity", _("By quantity")


class LandedCostDocument(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="landed_cost_documents",
    )
    purchase_invoice = models.OneToOneField(
        PurchaseInvoice,
        on_delete=models.CASCADE,
        related_name="landed_cost_document",
    )
    document_date = models.DateField()
    basis = models.CharField(
        max_length=16,
        choices=LandedCostBasis.choices,
        default=LandedCostBasis.BY_VALUE,
    )
    note = models.CharField(max_length=255, blank=True)
    is_applied = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    applied_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"LandedCost({self.purchase_invoice})"


class LandedCostLine(models.Model):
    document = models.ForeignKey(
        LandedCostDocument,
        on_delete=models.CASCADE,
        related_name="cost_lines",
    )
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    gl_account = models.ForeignKey(
        ChartOfAccount,
        on_delete=models.PROTECT,
        related_name="landed_cost_lines",
        help_text="Source account for this cost (freight expense, customs duty, etc.)",
    )

    def __str__(self) -> str:
        return f"{self.description} {self.amount}"


class LandedCostAllocation(models.Model):
    document = models.ForeignKey(
        LandedCostDocument,
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    purchase_line = models.ForeignKey(
        PurchaseInvoiceLine,
        on_delete=models.CASCADE,
        related_name="landed_cost_allocations",
    )
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    factor = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal("0"))

    def __str__(self) -> str:
        return f"{self.purchase_line} -> {self.amount}"
