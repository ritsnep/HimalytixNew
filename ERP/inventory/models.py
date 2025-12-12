# inventory/models.py  – Django 4.2+
from decimal import Decimal

from django.db import models
from django.utils import timezone
from mptt.models import MPTTModel, TreeForeignKey          # pip install django-mptt
from accounting.models import ChartOfAccount
from usermanagement.models import Organization               # your multi-tenant app
# from accounting.models import ChartOfAccount               # GL integration

# ---------- Master data ----------
class Unit(models.Model):
    """Unit of Measure (UOM) master"""
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    code         = models.CharField(max_length=10)
    name         = models.CharField(max_length=50)
    description  = models.TextField(blank=True)
    is_active    = models.BooleanField(default=True)
    created_at   = models.DateTimeField(default=timezone.now)
    
    class Meta:
        unique_together = ('organization', 'code')
    
    def __str__(self):
        return f"{self.organization.name} - {self.name} ({self.code})"


class ProductCategory(MPTTModel):
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    code         = models.CharField(max_length=50)
    name         = models.CharField(max_length=100)
    parent       = TreeForeignKey('self', null=True, blank=True,
                                  related_name='children', on_delete=models.PROTECT)
    is_active    = models.BooleanField(default=True)
    class MPTTMeta: order_insertion_by = ['name']
    class Meta: unique_together = ('organization', 'code')
    def __str__(self):
        return f"{self.organization.name} - {self.name} ({self.code})"

class Product(models.Model):
    organization       = models.ForeignKey(Organization, on_delete=models.PROTECT)
    category           = TreeForeignKey(ProductCategory, null=True, blank=True,
                                        on_delete=models.SET_NULL)
    code               = models.CharField(max_length=50)
    name               = models.CharField(max_length=200)
    description        = models.TextField(blank=True)
    base_unit          = models.ForeignKey(Unit, null=True, blank=True, on_delete=models.PROTECT)
    sale_price         = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    cost_price         = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    currency_code      = models.CharField(max_length=3, default="USD")
    income_account     = models.ForeignKey(ChartOfAccount, null=True, blank=True,
                                           related_name="income_products", on_delete=models.PROTECT)
    expense_account    = models.ForeignKey(ChartOfAccount, null=True, blank=True,
                                           related_name="expense_products", on_delete=models.PROTECT,
                                           help_text="COGS account for inventory items")
    inventory_account  = models.ForeignKey(ChartOfAccount, null=True, blank=True,
                                           related_name="inventory_products", on_delete=models.PROTECT,
                                           help_text="Asset account for inventory items")
    is_inventory_item  = models.BooleanField(default=False)
    min_order_quantity = models.DecimalField(max_digits=15, decimal_places=4, default=1)
    reorder_level      = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    preferred_vendor   = models.ForeignKey('accounting.Vendor', null=True, blank=True, on_delete=models.PROTECT)
    weight             = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    weight_unit        = models.ForeignKey(Unit, null=True, blank=True, related_name='weight_products', on_delete=models.PROTECT)
    length             = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    width              = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    height             = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    barcode            = models.CharField(max_length=100, blank=True)
    sku                = models.CharField(max_length=100, blank=True)
    created_at         = models.DateTimeField(default=timezone.now)
    updated_at         = models.DateTimeField(auto_now=True)
    
    class Meta: 
        unique_together = ('organization', 'code')
    
    def __str__(self):
        return f"{self.organization.name} - {self.name} ({self.code})"
    
    def clean(self):
        """Validate that inventory items have required GL accounts."""
        super().clean()
        if self.is_inventory_item:
            from django.core.exceptions import ValidationError
            errors = {}
            if not self.inventory_account:
                errors['inventory_account'] = 'Inventory account is required for inventory items.'
            if not self.expense_account:
                errors['expense_account'] = 'COGS (expense) account is required for inventory items.'
            if errors:
                raise ValidationError(errors)


class ProductUnit(models.Model):
    """Alternative units for products with conversion factors"""
    product           = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='units')
    unit              = models.ForeignKey(Unit, on_delete=models.PROTECT)
    conversion_factor = models.DecimalField(max_digits=15, decimal_places=6, help_text="Number of base units per this unit")
    is_default        = models.BooleanField(default=False)
    created_at        = models.DateTimeField(default=timezone.now)
    
    class Meta:
        unique_together = ('product', 'unit')
    
    def __str__(self):
        return f"{self.product.code} - {self.unit.code}: {self.conversion_factor}"


# ---------- Warehouse structure ----------
class Warehouse(models.Model):
    organization     = models.ForeignKey(Organization, on_delete=models.PROTECT)
    code             = models.CharField(max_length=50)
    name             = models.CharField(max_length=100)
    address_line1    = models.CharField(max_length=200)
    city             = models.CharField(max_length=100)
    country_code     = models.CharField(max_length=2, default='US')
    inventory_account= models.ForeignKey(ChartOfAccount, null=True, blank=True,
                                         on_delete=models.PROTECT)
    is_active        = models.BooleanField(default=True)
    class Meta: unique_together = ('organization', 'code')
    def __str__(self):
        return f"{self.organization.name} - {self.name} ({self.code})"

class Location(models.Model):
    warehouse     = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='locations')
    code          = models.CharField(max_length=50)          # e.g. A-01-R03-S02-B07
    name          = models.CharField(max_length=100, blank=True)
    location_type = models.CharField(max_length=50, choices=[
        ('storage', 'Storage'),
        ('staging', 'Staging'),
        ('qc', 'Quality Control'),
        ('shipping', 'Shipping'),
        ('receiving', 'Receiving'),
    ], default='storage')  # staging, QC …
    is_active     = models.BooleanField(default=True)
    class Meta: unique_together = ('warehouse', 'code')
    def __str__(self):
        return f"{self.warehouse.organization.name} - {self.warehouse.code} - {self.code}"

# ---------- Batch / serial ----------
class Batch(models.Model):
    organization    = models.ForeignKey(Organization, on_delete=models.PROTECT)
    product         = models.ForeignKey(Product, on_delete=models.PROTECT)
    batch_number    = models.CharField(max_length=100)
    serial_number   = models.CharField(max_length=100, blank=True)
    manufacture_date= models.DateField(null=True, blank=True)
    expiry_date     = models.DateField(null=True, blank=True)
    class Meta: unique_together = ('organization', 'product', 'batch_number', 'serial_number')
    def __str__(self):
        return f"{self.organization.name} - {self.product.code} - {self.batch_number}"

# ---------- Snapshot table ----------
class InventoryItem(models.Model):
    organization  = models.ForeignKey(Organization, on_delete=models.PROTECT)
    product       = models.ForeignKey(Product, on_delete=models.PROTECT)
    warehouse     = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    location      = models.ForeignKey(Location, null=True, blank=True, on_delete=models.PROTECT)
    batch         = models.ForeignKey(Batch, null=True, blank=True, on_delete=models.PROTECT)
    quantity_on_hand    = models.DecimalField(max_digits=15, decimal_places=4, default=Decimal("0"))
    quantity_allocated  = models.DecimalField(max_digits=15, decimal_places=4, default=Decimal("0"))
    quantity_available  = models.DecimalField(max_digits=15, decimal_places=4, default=Decimal("0"))
    unit_cost           = models.DecimalField(max_digits=19, decimal_places=4, default=Decimal("0"))
    total_cost          = models.DecimalField(max_digits=19, decimal_places=4, default=Decimal("0"))
    reorder_level       = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    reorder_quantity    = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    last_count_date     = models.DateTimeField(null=True, blank=True)
    last_received_date  = models.DateTimeField(null=True, blank=True)
    last_issued_date    = models.DateTimeField(null=True, blank=True)
    updated_at          = models.DateTimeField(auto_now=True)
    class Meta:
        unique_together = ('organization', 'product', 'warehouse', 'location', 'batch')
    def __str__(self):
        loc_code = self.location.code if self.location else 'N/A'
        batch_num = self.batch.batch_number if self.batch else 'N/A'
        return f"{self.organization.name} - {self.product.code} @ {self.warehouse.code}/{loc_code} ({batch_num}): {self.quantity_on_hand}"

# ---------- Immutable ledger ----------
class StockLedger(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    product      = models.ForeignKey(Product, on_delete=models.PROTECT)
    warehouse    = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    location     = models.ForeignKey(Location, null=True, blank=True, on_delete=models.PROTECT)
    batch        = models.ForeignKey(Batch, null=True, blank=True, on_delete=models.PROTECT)
    txn_type     = models.CharField(max_length=30)         # purchase, sale, transfer, adj …
    reference_id = models.CharField(max_length=100)        # PO, SO, etc.
    txn_date     = models.DateTimeField()
    qty_in       = models.DecimalField(max_digits=15, decimal_places=4, default=Decimal("0"))
    qty_out      = models.DecimalField(max_digits=15, decimal_places=4, default=Decimal("0"))
    unit_cost    = models.DecimalField(max_digits=19, decimal_places=4, default=Decimal("0"))  # moving-avg
    total_cost   = models.DecimalField(max_digits=19, decimal_places=4, default=Decimal("0"))
    created_at   = models.DateTimeField(default=timezone.now)
    class Meta:
        indexes = [models.Index(fields=['organization', 'product', 'warehouse'])]
        ordering = ('-txn_date', '-id')
    def __str__(self):
        loc_code = self.location.code if self.location else 'N/A'
        batch_num = self.batch.batch_number if self.batch else 'N/A'
        return f"{self.organization.name} - {self.txn_type} {self.product.code} @ {self.warehouse.code}/{loc_code} ({batch_num}): +{self.qty_in}/-{self.qty_out}"


class StockLedgerReport(StockLedger):
    class Meta:
        proxy = True
        verbose_name = "Stock Ledger Report"
        verbose_name_plural = "Stock Ledger Report"


class StockSummary(InventoryItem):
    class Meta:
        proxy = True
        verbose_name = "Stock Summary"
        verbose_name_plural = "Stock Summary"


# ---------- Pricing & Promotions ----------
class PriceList(models.Model):
    """Price list for multi-tier pricing (standard, wholesale, retail, distributor)"""
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    code         = models.CharField(max_length=50)
    name         = models.CharField(max_length=100)
    description  = models.TextField(blank=True)
    currency_code= models.CharField(max_length=3, default="USD")
    is_active    = models.BooleanField(default=True)
    valid_from   = models.DateField(null=True, blank=True)
    valid_to     = models.DateField(null=True, blank=True)
    created_at   = models.DateTimeField(default=timezone.now)
    updated_at   = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('organization', 'code')
        indexes = [models.Index(fields=['organization', 'is_active'])]
    
    def __str__(self):
        return f"{self.organization.name} - {self.name} ({self.code})"


class PriceListItem(models.Model):
    """Individual product prices within a price list"""
    price_list   = models.ForeignKey(PriceList, on_delete=models.CASCADE, related_name='items')
    product      = models.ForeignKey(Product, on_delete=models.PROTECT)
    unit_price   = models.DecimalField(max_digits=19, decimal_places=4)
    min_quantity = models.DecimalField(max_digits=15, decimal_places=4, default=1)  # MOQ per price tier
    max_quantity = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    created_at   = models.DateTimeField(default=timezone.now)
    updated_at   = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('price_list', 'product', 'min_quantity')
        indexes = [models.Index(fields=['price_list', 'product'])]
    
    def __str__(self):
        return f"{self.price_list.name} - {self.product.code}: {self.unit_price} (MOQ: {self.min_quantity})"


class CustomerPriceList(models.Model):
    """Assign specific price lists to customers"""
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    customer_id  = models.IntegerField()  # FK to Customer model in billing/CRM
    price_list   = models.ForeignKey(PriceList, on_delete=models.PROTECT)
    priority     = models.IntegerField(default=1)  # Lower number = higher priority
    is_active    = models.BooleanField(default=True)
    created_at   = models.DateTimeField(default=timezone.now)
    
    class Meta:
        unique_together = ('organization', 'customer_id', 'price_list')
        indexes = [models.Index(fields=['organization', 'customer_id', 'is_active'])]
    
    def __str__(self):
        return f"{self.organization.name} - Customer {self.customer_id} - {self.price_list.name}"


class PromotionRule(models.Model):
    """Promotional discounts and offers (seasonal, clearance, BOGO)"""
    PROMO_TYPES = [
        ('percentage', 'Percentage Discount'),
        ('fixed', 'Fixed Amount Discount'),
        ('bogo', 'Buy One Get One'),
        ('bundle', 'Bundle Discount'),
        ('volume', 'Volume Discount'),
    ]
    
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    code         = models.CharField(max_length=50)
    name         = models.CharField(max_length=100)
    description  = models.TextField(blank=True)
    promo_type   = models.CharField(max_length=20, choices=PROMO_TYPES, default='percentage')
    discount_value = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    min_purchase_amount = models.DecimalField(max_digits=19, decimal_places=4, null=True, blank=True)
    valid_from   = models.DateTimeField()
    valid_to     = models.DateTimeField()
    is_active    = models.BooleanField(default=True)
    max_uses     = models.IntegerField(null=True, blank=True)
    current_uses = models.IntegerField(default=0)
    apply_to_products = models.ManyToManyField(Product, blank=True, related_name='promotions')
    created_at   = models.DateTimeField(default=timezone.now)
    updated_at   = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('organization', 'code')
        indexes = [
            models.Index(fields=['organization', 'is_active', 'valid_from', 'valid_to'])
        ]
    
    def __str__(self):
        return f"{self.organization.name} - {self.name} ({self.promo_type})"
    
    def is_valid(self):
        """Check if promotion is currently valid"""
        now = timezone.now()
        if not self.is_active:
            return False
        if self.valid_from > now or self.valid_to < now:
            return False
        if self.max_uses and self.current_uses >= self.max_uses:
            return False
        return True


# ---------- Fulfillment Workflow ----------
class TransitWarehouse(models.Model):
    """Virtual warehouse for goods in transit between locations"""
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    code         = models.CharField(max_length=50)
    name         = models.CharField(max_length=100)
    from_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, 
                                       related_name='transit_from', null=True, blank=True)
    to_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, 
                                     related_name='transit_to', null=True, blank=True)
    carrier_name = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    is_active    = models.BooleanField(default=True)
    created_at   = models.DateTimeField(default=timezone.now)
    
    class Meta:
        unique_together = ('organization', 'code')
    
    def __str__(self):
        return f"{self.organization.name} - {self.name} (Transit)"


class PickList(models.Model):
    """Pick list for warehouse picking operations"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('released', 'Released'),
        ('picking', 'Picking In Progress'),
        ('picked', 'Picked'),
        ('cancelled', 'Cancelled'),
    ]
    
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    pick_number  = models.CharField(max_length=50, unique=True)
    warehouse    = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    order_reference = models.CharField(max_length=100)  # Sales Order, Transfer Order
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    priority     = models.IntegerField(default=5)  # 1=urgent, 10=low
    assigned_to  = models.IntegerField(null=True, blank=True)  # User ID
    pick_date    = models.DateTimeField(null=True, blank=True)
    completed_date = models.DateTimeField(null=True, blank=True)
    notes        = models.TextField(blank=True)
    created_at   = models.DateTimeField(default=timezone.now)
    updated_at   = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['organization', 'warehouse', 'status']),
            models.Index(fields=['pick_number'])
        ]
    
    def __str__(self):
        return f"{self.organization.name} - {self.pick_number} ({self.status})"


class PickListLine(models.Model):
    """Line items for pick list"""
    pick_list    = models.ForeignKey(PickList, on_delete=models.CASCADE, related_name='lines')
    product      = models.ForeignKey(Product, on_delete=models.PROTECT)
    location     = models.ForeignKey(Location, on_delete=models.PROTECT, null=True, blank=True)
    batch        = models.ForeignKey(Batch, on_delete=models.PROTECT, null=True, blank=True)
    quantity_ordered = models.DecimalField(max_digits=15, decimal_places=4)
    quantity_picked  = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    line_number  = models.IntegerField()
    picked_by    = models.IntegerField(null=True, blank=True)  # User ID
    picked_at    = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ('pick_list', 'line_number')
        ordering = ['line_number']
    
    def __str__(self):
        return f"{self.pick_list.pick_number} - Line {self.line_number}: {self.product.code}"


class PackingSlip(models.Model):
    """Packing slip for packed goods"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('packing', 'Packing In Progress'),
        ('packed', 'Packed'),
        ('cancelled', 'Cancelled'),
    ]
    
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    packing_number = models.CharField(max_length=50, unique=True)
    pick_list    = models.ForeignKey(PickList, on_delete=models.PROTECT, null=True, blank=True)
    warehouse    = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    order_reference = models.CharField(max_length=100)
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    packed_by    = models.IntegerField(null=True, blank=True)  # User ID
    packed_date  = models.DateTimeField(null=True, blank=True)
    num_packages = models.IntegerField(default=1)
    total_weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes        = models.TextField(blank=True)
    created_at   = models.DateTimeField(default=timezone.now)
    updated_at   = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [models.Index(fields=['organization', 'status'])]
    
    def __str__(self):
        return f"{self.organization.name} - {self.packing_number} ({self.status})"


class Shipment(models.Model):
    """Shipment tracking for outbound deliveries"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('picked_up', 'Picked Up'),
        ('in_transit', 'In Transit'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('failed', 'Delivery Failed'),
        ('returned', 'Returned'),
    ]
    
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    shipment_number = models.CharField(max_length=50, unique=True)
    packing_slip = models.ForeignKey(PackingSlip, on_delete=models.PROTECT, null=True, blank=True)
    order_reference = models.CharField(max_length=100)
    carrier_name = models.CharField(max_length=100)
    tracking_number = models.CharField(max_length=100, blank=True)
    service_type = models.CharField(max_length=50, blank=True)  # Ground, Express, etc.
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    ship_from_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    ship_to_address = models.TextField()
    estimated_delivery = models.DateField(null=True, blank=True)
    actual_delivery = models.DateField(null=True, blank=True)
    shipping_cost = models.DecimalField(max_digits=19, decimal_places=4, null=True, blank=True)
    notes        = models.TextField(blank=True)
    created_at   = models.DateTimeField(default=timezone.now)
    updated_at   = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['tracking_number'])
        ]
    
    def __str__(self):
        return f"{self.organization.name} - {self.shipment_number} ({self.carrier_name})"


class Backorder(models.Model):
    """Track backorders for unfulfilled demand"""
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    backorder_number = models.CharField(max_length=50, unique=True)
    order_reference = models.CharField(max_length=100)
    product      = models.ForeignKey(Product, on_delete=models.PROTECT)
    warehouse    = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    quantity_backordered = models.DecimalField(max_digits=15, decimal_places=4)
    quantity_fulfilled = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    customer_id  = models.IntegerField(null=True, blank=True)
    expected_date = models.DateField(null=True, blank=True)
    priority     = models.IntegerField(default=5)
    is_fulfilled = models.BooleanField(default=False)
    notes        = models.TextField(blank=True)
    created_at   = models.DateTimeField(default=timezone.now)
    updated_at   = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['organization', 'is_fulfilled', 'priority']),
            models.Index(fields=['product', 'warehouse'])
        ]
    
    def __str__(self):
        return f"{self.organization.name} - {self.backorder_number}: {self.product.code} ({self.quantity_backordered})"
    
    @property
    def quantity_remaining(self):
        return self.quantity_backordered - self.quantity_fulfilled


class RMA(models.Model):
    """Return Merchandise Authorization"""
    STATUS_CHOICES = [
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('received', 'Received'),
        ('inspected', 'Inspected'),
        ('refunded', 'Refunded'),
        ('replaced', 'Replaced'),
        ('closed', 'Closed'),
    ]
    
    REASON_CHOICES = [
        ('defective', 'Defective'),
        ('wrong_item', 'Wrong Item Sent'),
        ('damaged', 'Damaged in Transit'),
        ('not_needed', 'No Longer Needed'),
        ('warranty', 'Warranty Claim'),
        ('other', 'Other'),
    ]
    
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    rma_number   = models.CharField(max_length=50, unique=True)
    customer_id  = models.IntegerField()
    original_order = models.CharField(max_length=100)
    original_invoice = models.CharField(max_length=100, blank=True)
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default='requested')
    reason       = models.CharField(max_length=20, choices=REASON_CHOICES)
    description  = models.TextField()
    requested_date = models.DateTimeField(default=timezone.now)
    approved_date = models.DateTimeField(null=True, blank=True)
    approved_by  = models.IntegerField(null=True, blank=True)  # User ID
    warehouse    = models.ForeignKey(Warehouse, on_delete=models.PROTECT, null=True, blank=True)
    resolution   = models.CharField(max_length=20, blank=True)  # refund, replace, repair
    refund_amount = models.DecimalField(max_digits=19, decimal_places=4, null=True, blank=True)
    restocking_fee = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    notes        = models.TextField(blank=True)
    created_at   = models.DateTimeField(default=timezone.now)
    updated_at   = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['customer_id'])
        ]
    
    def __str__(self):
        return f"{self.organization.name} - RMA {self.rma_number} ({self.status})"


class RMALine(models.Model):
    """Line items for RMA"""
    rma          = models.ForeignKey(RMA, on_delete=models.CASCADE, related_name='lines')
    product      = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity_returned = models.DecimalField(max_digits=15, decimal_places=4)
    batch        = models.ForeignKey(Batch, on_delete=models.PROTECT, null=True, blank=True)
    condition    = models.CharField(max_length=50, blank=True)  # new, used, defective
    disposition  = models.CharField(max_length=50, blank=True)  # restock, scrap, repair
    line_number  = models.IntegerField()
    
    class Meta:
        unique_together = ('rma', 'line_number')
        ordering = ['line_number']
    
    def __str__(self):
        return f"RMA {self.rma.rma_number} - Line {self.line_number}: {self.product.code}"
