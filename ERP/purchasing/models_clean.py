from __future__ import annotations

from decimal import Decimal
from django.utils import timezone
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _
from django.conf import settings

from inventory.models import Product, Warehouse
from accounting.models import ChartOfAccount, Currency, Vendor
from usermanagement.models import Organization

# ============================================================================
# CONSOLIDATED MODELS - Now imported from accounting app (single source of truth)
# ============================================================================
# The following models have been consolidated into accounting.models:
# - PurchaseInvoice
# - PurchaseInvoiceLine
# - PurchaseInvoiceAdditionalCharge
# - LandedCostDocument
# - LandedCostLine
# - LandedCostAllocation
# - LandedCostBasis
#
# Import them from accounting to maintain compatibility:
from accounting.models import (
    PurchaseInvoice,
    PurchaseInvoiceLine,
    PurchaseInvoiceAdditionalCharge,
    LandedCostDocument,
    LandedCostLine,
    LandedCostAllocation,
    LandedCostBasis,
)

# ============================================================================
# PURCHASING-SPECIFIC MODELS (Unique to this app)
# ============================================================================
# The following models remain in purchasing app as they are procurement-specific:
# - PurchaseOrder / PurchaseOrderLine
# - GoodsReceipt / GoodsReceiptLine


# ============================================================================
# PURCHASE ORDER & GOODS RECEIPT MODELS
# ============================================================================

class PurchaseOrder(models.Model):
    """Purchase Order model for procurement planning."""
    
    class Status(models.TextChoices):
        DRAFT = "draft", _("Draft")
        APPROVED = "approved", _("Approved")
        SENT = "sent", _("Sent to Vendor")
        RECEIVED = "received", _("Received")
        CLOSED = "closed", _("Closed")

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="purchase_orders",
    )
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )
    
    # Metadata
    number = models.CharField(max_length=64)
    order_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=16, 
        choices=Status.choices, 
        default=Status.DRAFT
    )
    
    # Currency & amounts
    currency = models.ForeignKey(
        Currency, 
        on_delete=models.PROTECT
    )
    exchange_rate = models.DecimalField(
        max_digits=18, 
        decimal_places=6, 
        default=Decimal("1")
    )
    subtotal = models.DecimalField(
        max_digits=18, 
        decimal_places=2, 
        default=Decimal("0")
    )
    tax_amount = models.DecimalField(
        max_digits=18, 
        decimal_places=2, 
        default=Decimal("0")
    )
    total_amount = models.DecimalField(
        max_digits=18, 
        decimal_places=2, 
        default=Decimal("0")
    )
    
    # Tracking
    send_date = models.DateField(null=True, blank=True)
    expected_receipt_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    # Audit
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name="created_purchase_orders"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ("organization", "number")
        ordering = ("-order_date", "-id")
        indexes = [
            models.Index(fields=["organization", "status", "order_date"]),
            models.Index(fields=["vendor", "status"]),
        ]
    
    def __str__(self) -> str:
        return f"PO-{self.number}"
    
    def recalc_totals(self):
        """Recompute subtotal/tax/total from the order lines."""
        subtotal = Decimal("0")
        tax = Decimal("0")
        for line in self.lines.all():
            line_total = line.quantity_ordered * line.unit_price
            subtotal += line_total
            tax += line_total * (line.vat_rate / Decimal("100"))
        self.subtotal = subtotal.quantize(Decimal("0.01"))
        self.tax_amount = tax.quantize(Decimal("0.01"))
        self.total_amount = (self.subtotal + self.tax_amount).quantize(Decimal("0.01"))

    def save(self, *args, **kwargs):
        skip_recalc = kwargs.pop("skip_recalc", False)
        if self.pk and not skip_recalc:
            self.recalc_totals()
        super().save(*args, **kwargs)


class PurchaseOrderLine(models.Model):
    """Individual line items on a purchase order."""
    
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="purchase_order_lines",
    )
    
    # Order details
    quantity_ordered = models.DecimalField(max_digits=18, decimal_places=4)
    unit_price = models.DecimalField(max_digits=18, decimal_places=4)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0"))
    expected_delivery_date = models.DateField(null=True, blank=True)
    
    # Tracking
    quantity_received = models.DecimalField(
        max_digits=18, 
        decimal_places=4, 
        default=Decimal("0")
    )
    quantity_invoiced = models.DecimalField(
        max_digits=18, 
        decimal_places=4, 
        default=Decimal("0")
    )
    
    # GL accounts
    inventory_account = models.ForeignKey(
        ChartOfAccount,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="po_inventory_lines"
    )
    expense_account = models.ForeignKey(
        ChartOfAccount,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="po_expense_lines"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self) -> str:
        return f"{self.product} x {self.quantity_ordered}"
    
    @property
    def line_total(self) -> Decimal:
        return (self.quantity_ordered * self.unit_price).quantize(Decimal("0.01"))
    
    @property
    def variance(self) -> Decimal:
        """Outstanding quantity: ordered - (received + invoiced)"""
        return self.quantity_ordered - (self.quantity_received + self.quantity_invoiced)


class GoodsReceipt(models.Model):
    """Goods receipt tracking receiving shipments against purchase orders."""
    
    class Status(models.TextChoices):
        DRAFT = "draft", _("Draft")
        RECEIVED = "received", _("Goods Received")
        INSPECTED = "inspected", _("Inspected/QC Passed")
        POSTED = "posted", _("Posted to Inventory")
        CANCELLED = "cancelled", _("Cancelled")
    
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="goods_receipts",
    )
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.PROTECT,
        related_name="receipts",
    )
    
    # Receipt info
    number = models.CharField(max_length=64)
    receipt_date = models.DateField()
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="goods_receipts",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT
    )
    
    # Reference (optional ASN/shipment number from vendor)
    reference_number = models.CharField(max_length=64, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    qc_notes = models.TextField(blank=True)
    
    # GL posting
    journal = models.OneToOneField(
        "accounting.Journal",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="goods_receipt",
    )
    
    # Audit
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_goods_receipts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ("organization", "number")
        ordering = ("-receipt_date", "-id")
        indexes = [
            models.Index(fields=["organization", "status", "receipt_date"]),
            models.Index(fields=["purchase_order", "status"]),
        ]
    
    def __str__(self) -> str:
        return f"GR-{self.number}"


class GoodsReceiptLine(models.Model):
    """Individual line items on a goods receipt."""
    
    receipt = models.ForeignKey(
        GoodsReceipt,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    po_line = models.ForeignKey(
        PurchaseOrderLine,
        on_delete=models.PROTECT,
        related_name="receipt_lines",
    )
    
    # Received quantities
    quantity_received = models.DecimalField(max_digits=18, decimal_places=4)
    quantity_accepted = models.DecimalField(
        max_digits=18, 
        decimal_places=4, 
        default=Decimal("0")
    )
    quantity_rejected = models.DecimalField(
        max_digits=18, 
        decimal_places=4, 
        default=Decimal("0")
    )
    
    # Tracking
    serial_numbers = models.TextField(
        blank=True,
        help_text="Comma-separated if applicable"
    )
    batch_number = models.CharField(max_length=64, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    qc_result = models.CharField(
        max_length=16,
        choices=[
            ("pass", _("Passed")),
            ("fail", _("Failed")),
            ("pending", _("Pending"))
        ],
        default="pending"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self) -> str:
        return f"GR Line: {self.po_line.product} x {self.quantity_received}"
    
    @property
    def variance(self) -> Decimal:
        """Quantity over/under expected"""
        return self.quantity_received - self.po_line.quantity_ordered
