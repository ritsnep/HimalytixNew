from django.db import models


class CylinderType(models.Model):
    """
    Master for LPG cylinder sizes (e.g. 14.2kg, 5kg, 19kg).
    NOTE: In a real project you will likely want to add a foreign key
    to your Company/Tenant model here.
    """
    name = models.CharField(max_length=50, help_text="Display name, e.g. 14.2 kg")
    kg_per_cylinder = models.DecimalField(max_digits=8, decimal_places=3)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.kg_per_cylinder} kg)"


class CylinderSKU(models.Model):
    """
    Represents a SKUs for filled/empty variants for each cylinder type.
    Example:
      - 14.2kg Filled
      - 14.2kg Empty
    """
    STATE_FILLED = "filled"
    STATE_EMPTY = "empty"
    STATE_CHOICES = [
        (STATE_FILLED, "Filled"),
        (STATE_EMPTY, "Empty"),
    ]

    name = models.CharField(max_length=80)
    cylinder_type = models.ForeignKey(CylinderType, on_delete=models.CASCADE, related_name="skus")
    state = models.CharField(max_length=10, choices=STATE_CHOICES)
    code = models.CharField(max_length=32, unique=True)

    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.name} [{self.code}]"


class ConversionRule(models.Model):
    """
    Conversion from LPG mass (in metric tons) to cylinders.

    Example:
        1 MT -> 70 cylinders of 14.2kg
    """
    cylinder_type = models.ForeignKey(CylinderType, on_delete=models.CASCADE, related_name="conversion_rules")
    mt_per_cylinder = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        help_text="How many metric tons are consumed per 1 cylinder of this type.",
    )
    is_default = models.BooleanField(
        default=True,
        help_text="Mark the default rule per cylinder type for allocation logic."
    )

    class Meta:
        unique_together = ("cylinder_type", "is_default")

    def __str__(self) -> str:
        return f"{self.cylinder_type} – {self.mt_per_cylinder} MT / cylinder"


class NocPurchase(models.Model):
    """
    High-level representation of LPG purchases from NOC in metric tons.

    This model is designed to sit on top of your existing purchasing /
    accounting layer. You can:
      - Add a OneToOneField to your existing Purchase/Voucher model, OR
      - Use the data here to create the underlying voucher when 'posted'.
    """
    STATUS_DRAFT = "draft"
    STATUS_POSTED = "posted"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_POSTED, "Posted to Accounting/Inventory"),
    ]

    bill_no = models.CharField(max_length=50)
    purchase_date = models.DateField()
    quantity_mt = models.DecimalField(max_digits=12, decimal_places=3)
    rate_per_mt = models.DecimalField(max_digits=12, decimal_places=2)
    transport_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Optional integration hook: link this to your own purchase/voucher table once implemented.
    # base_purchase = models.OneToOneField("accounting.PurchaseVoucher", ...)

    class Meta:
        ordering = ("-purchase_date", "-id")

    @property
    def subtotal(self):
        return self.quantity_mt * self.rate_per_mt

    @property
    def total_amount(self):
        return self.subtotal + self.transport_cost + self.tax_amount

    def __str__(self) -> str:
        return f"NOC Purchase {self.bill_no} – {self.purchase_date}"


class LogisticsTrip(models.Model):
    """
    Trip-wise logistics entry: how many cylinders moved, where, at what cost.

    In integration, you can:
      - Link to a TransportProvider / Vehicle master in your existing DB.
      - Generate inventory transfer movements between locations.
    """
    trip_date = models.DateField()
    transport_provider_name = models.CharField(max_length=128)
    vehicle_number = models.CharField(max_length=32)
    from_location = models.CharField(max_length=128)
    to_location = models.CharField(max_length=128)
    cylinder_count = models.PositiveIntegerField()
    cost = models.DecimalField(max_digits=12, decimal_places=2)

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-trip_date", "-id")

    def __str__(self) -> str:
        return f"{self.trip_date} – {self.vehicle_number} [{self.cylinder_count} cyl]"
