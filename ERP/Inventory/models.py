# inventory/models.py  – Django 4.2+
from django.db import models
from django.utils import timezone
from mptt.models import MPTTModel, TreeForeignKey          # pip install django-mptt
from accounting.models import ChartOfAccount
from usermanagement.models import Organization               # your multi-tenant app
# from accounting.models import ChartOfAccount               # GL integration

# ---------- Master data ----------
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
    uom                = models.CharField(max_length=50, default="each")
    sale_price         = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    cost_price         = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    currency_code      = models.CharField(max_length=3, default="USD")
    income_account     = models.ForeignKey(ChartOfAccount, null=True, blank=True,
                                           related_name="income_products", on_delete=models.PROTECT)
    expense_account    = models.ForeignKey(ChartOfAccount, null=True, blank=True,
                                           related_name="expense_products", on_delete=models.PROTECT)
    inventory_account  = models.ForeignKey(ChartOfAccount, null=True, blank=True,
                                           related_name="inventory_products", on_delete=models.PROTECT)
    is_inventory_item  = models.BooleanField(default=False)
    min_order_quantity = models.DecimalField(max_digits=15, decimal_places=4, default=1)
    reorder_level      = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    preferred_vendor_id= models.IntegerField(null=True, blank=True)
    barcode            = models.CharField(max_length=100, blank=True)
    sku                = models.CharField(max_length=100, blank=True)
    created_at         = models.DateTimeField(default=timezone.now)
    updated_at         = models.DateTimeField(auto_now=True)
    class Meta: unique_together = ('organization', 'code')
    def __str__(self):
        return f"{self.organization.name} - {self.name} ({self.code})"

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
    location_type = models.CharField(max_length=50, default='storage')  # staging, QC …
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
    quantity_on_hand = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    unit_cost        = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    updated_at       = models.DateTimeField(auto_now=True)
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
    qty_in       = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    qty_out      = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    unit_cost    = models.DecimalField(max_digits=19, decimal_places=4, default=0)  # moving-avg
    created_at   = models.DateTimeField(default=timezone.now)
    class Meta:
        indexes = [models.Index(fields=['organization', 'product', 'warehouse'])]
    def __str__(self):
        loc_code = self.location.code if self.location else 'N/A'
        batch_num = self.batch.batch_number if self.batch else 'N/A'
        return f"{self.organization.name} - {self.txn_type} {self.product.code} @ {self.warehouse.code}/{loc_code} ({batch_num}): +{self.qty_in}/-{self.qty_out}"
