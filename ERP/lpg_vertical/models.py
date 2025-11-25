from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from usermanagement.models import Organization

User = get_user_model()


class TimeStampedScopedModel(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="%(class)ss",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class LpgProduct(TimeStampedScopedModel):
    """Generic LPG product (bulk or generic cylinder contents)."""

    code = models.CharField(max_length=50)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    is_bulk = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("organization", "code")
        ordering = ("organization", "code")

    def __str__(self):
        return f"{self.organization.code} - {self.name}"


class CylinderType(TimeStampedScopedModel):
    name = models.CharField(max_length=50, help_text="Display name, e.g. 14.2 kg")
    kg_per_cylinder = models.DecimalField(max_digits=8, decimal_places=3)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("organization", "name")
        ordering = ("organization", "kg_per_cylinder")

    def __str__(self) -> str:
        return f"{self.name} ({self.kg_per_cylinder} kg)"


class CylinderSKU(TimeStampedScopedModel):
    STATE_FILLED = "filled"
    STATE_EMPTY = "empty"
    STATE_CHOICES = [
        (STATE_FILLED, "Filled"),
        (STATE_EMPTY, "Empty"),
    ]

    name = models.CharField(max_length=80)
    cylinder_type = models.ForeignKey(CylinderType, on_delete=models.CASCADE, related_name="skus")
    state = models.CharField(max_length=10, choices=STATE_CHOICES)
    code = models.CharField(max_length=32)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("organization", "code")
        ordering = ("organization", "code")

    def __str__(self) -> str:
        return f"{self.name} [{self.code}]"


class ConversionRule(TimeStampedScopedModel):
    cylinder_type = models.ForeignKey(CylinderType, on_delete=models.CASCADE, related_name="conversion_rules")
    mt_fraction_per_cylinder = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        help_text="How many metric tons are consumed per 1 cylinder of this type.",
    )
    is_default = models.BooleanField(
        default=True,
        help_text="Mark the default rule per cylinder type for allocation logic.",
    )

    class Meta:
        unique_together = ("organization", "cylinder_type", "is_default")

    def __str__(self) -> str:
        return f"{self.cylinder_type} @ {self.mt_fraction_per_cylinder} MT / cylinder"


class Dealer(TimeStampedScopedModel):
    company_code = models.CharField(max_length=30)
    name = models.CharField(max_length=150)
    contact_person = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    tax_id = models.CharField(max_length=50, blank=True)
    credit_limit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("organization", "company_code")
        ordering = ("organization", "company_code")

    def __str__(self) -> str:
        return f"{self.company_code} - {self.name}"


class TransportProvider(TimeStampedScopedModel):
    name = models.CharField(max_length=150)
    contact = models.CharField(max_length=150, blank=True)

    class Meta:
        unique_together = ("organization", "name")
        ordering = ("organization", "name")

    def __str__(self) -> str:
        return self.name


class Vehicle(TimeStampedScopedModel):
    number = models.CharField(max_length=50)
    provider = models.ForeignKey(TransportProvider, on_delete=models.PROTECT, related_name="vehicles")
    capacity = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("organization", "number")
        ordering = ("organization", "number")

    def __str__(self) -> str:
        return self.number


class InventoryMovement(TimeStampedScopedModel):
    MOVEMENT_CHOICES = [
        ("purchase_noc", "NOC Purchase"),
        ("sale", "Sale"),
        ("empty_collection", "Empty Collection"),
        ("refill", "Refill"),
        ("damage_loss", "Damage/Loss"),
        ("transfer_out", "Transfer Out"),
        ("transfer_in", "Transfer In"),
    ]

    date = models.DateField(default=timezone.now)
    cylinder_sku = models.ForeignKey(CylinderSKU, on_delete=models.PROTECT, related_name="movements")
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_CHOICES)
    source_location = models.CharField(max_length=128, blank=True)
    dest_location = models.CharField(max_length=128, blank=True)
    ref_doc_type = models.CharField(max_length=50, blank=True)
    ref_doc_id = models.IntegerField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ("-date", "-id")

    @property
    def signed_quantity(self):
        outbound_types = {"sale", "damage_loss", "transfer_out"}
        sign = Decimal("-1") if self.movement_type in outbound_types else Decimal("1")
        return (self.quantity or Decimal("0")) * sign


class NocPurchase(TimeStampedScopedModel):
    STATUS_DRAFT = "draft"
    STATUS_POSTED = "posted"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_POSTED, "Posted to Accounting/Inventory"),
    ]

    bill_no = models.CharField(max_length=50)
    date = models.DateField()
    quantity_mt = models.DecimalField(max_digits=12, decimal_places=3)
    rate_per_mt = models.DecimalField(max_digits=12, decimal_places=2)
    transport_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    receipt_location = models.CharField(max_length=128, blank=True)

    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    posted_journal = models.ForeignKey(
        "accounting.Journal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lpg_noc_purchases",
    )
    allocation_snapshot = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-date", "-id")
        unique_together = ("organization", "bill_no")

    @property
    def subtotal(self):
        return (self.quantity_mt or Decimal("0")) * (self.rate_per_mt or Decimal("0"))

    @property
    def total_amount(self):
        return self.subtotal + (self.transport_cost or Decimal("0")) + (self.tax_amount or Decimal("0"))

    def __str__(self) -> str:
        return f"NOC Purchase {self.bill_no} @ {self.date}"


class SalesInvoice(TimeStampedScopedModel):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("posted", "Posted"),
        ("cancelled", "Cancelled"),
    ]
    PAYMENT_CHOICES = [
        ("cash", "Cash"),
        ("credit", "Credit"),
        ("bank", "Bank"),
    ]

    date = models.DateField(default=timezone.now)
    invoice_no = models.CharField(max_length=50)
    dealer = models.ForeignKey(Dealer, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")
    payment_type = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default="cash")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    empty_cylinders_collected = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    posted_journal = models.ForeignKey(
        "accounting.Journal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lpg_sales_invoices",
    )

    taxable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        unique_together = ("organization", "invoice_no")
        ordering = ("-date", "-id")

    def __str__(self):
        return f"{self.invoice_no} ({self.organization.code})"

    def recompute_totals(self):
        aggregates = self.lines.aggregate(
            taxable=Sum("line_total"),
            tax=Sum("tax_amount"),
        )
        self.taxable_amount = aggregates.get("taxable") or Decimal("0")
        self.tax_amount = aggregates.get("tax") or Decimal("0")
        self.total_amount = (self.taxable_amount or Decimal("0")) + (self.tax_amount or Decimal("0"))
        return self.total_amount


class SalesInvoiceLine(TimeStampedScopedModel):
    invoice = models.ForeignKey(SalesInvoice, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(LpgProduct, on_delete=models.SET_NULL, null=True, blank=True)
    cylinder_sku = models.ForeignKey(CylinderSKU, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    rate = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ("invoice", "id")

    def clean(self):
        if not self.product and not self.cylinder_sku:
            raise ValidationError("Either product or cylinder_sku must be set on SalesInvoiceLine.")

    def compute_totals(self):
        base = (self.quantity or Decimal("0")) * (self.rate or Decimal("0"))
        discounted = base - (self.discount or Decimal("0"))
        self.tax_amount = discounted * (self.tax_rate or Decimal("0")) / Decimal("100")
        self.line_total = discounted
        return self.line_total


class LogisticsTrip(TimeStampedScopedModel):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("posted", "Posted"),
    ]

    date = models.DateField(default=timezone.now)
    provider = models.ForeignKey(TransportProvider, on_delete=models.PROTECT, related_name="trips")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="trips")
    from_location = models.CharField(max_length=128)
    to_location = models.CharField(max_length=128)
    cylinder_sku = models.ForeignKey(CylinderSKU, on_delete=models.PROTECT, related_name="logistics_trips")
    cylinder_count = models.PositiveIntegerField()
    cost = models.DecimalField(max_digits=12, decimal_places=2)
    ref_doc_type = models.CharField(max_length=50, blank=True)
    ref_doc_id = models.IntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")
    posted_journal = models.ForeignKey(
        "accounting.Journal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lpg_logistics_trips",
    )

    class Meta:
        ordering = ("-date", "-id")

    def __str__(self) -> str:
        return f"{self.date} - {self.vehicle.number} [{self.cylinder_count} cyl]"
