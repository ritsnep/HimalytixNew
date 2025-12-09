from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from usermanagement.models import Organization
from inventory.models import Product
from decimal import Decimal

User = get_user_model()

class Cart(models.Model):
    """Temporary cart for POS transactions."""

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    cart_id = models.AutoField(primary_key=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    customer_name = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    subtotal = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    tax_total = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    total = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'pos_cart'
        ordering = ['-created_at']

    def __str__(self):
        return f"Cart {self.cart_id} - {self.customer_name or 'Walk-in'}"

    def recalculate_totals(self):
        """Recalculate cart totals from items."""
        items = self.items.all()
        self.subtotal = sum(item.line_total for item in items)
        self.tax_total = sum(item.tax_amount for item in items)
        self.total = self.subtotal + self.tax_total
        self.save(update_fields=['subtotal', 'tax_total', 'total', 'updated_at'])


class CartItem(models.Model):
    """Items in a POS cart."""

    cart_item_id = models.AutoField(primary_key=True)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    product_name = models.CharField(max_length=200)  # Snapshot for display
    product_code = models.CharField(max_length=50)   # Snapshot for display
    barcode = models.CharField(max_length=100, blank=True)  # Snapshot
    quantity = models.DecimalField(max_digits=19, decimal_places=4, default=1)
    unit_price = models.DecimalField(max_digits=19, decimal_places=6, default=0)
    discount_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    line_total = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    tax_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'pos_cart_item'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"

    def save(self, *args, **kwargs):
        """Calculate line total when saving."""
        self.line_total = (self.quantity * self.unit_price) - self.discount_amount
        super().save(*args, **kwargs)


class POSSettings(models.Model):
    """POS-specific settings per organization."""

    organization = models.OneToOneField(Organization, on_delete=models.CASCADE)
    default_customer_name = models.CharField(max_length=255, default='Walk-in Customer')
    enable_barcode_scanner = models.BooleanField(default=True)
    enable_camera_scanner = models.BooleanField(default=False)
    show_item_images = models.BooleanField(default=True)
    receipt_printer_name = models.CharField(max_length=255, blank=True)
    cash_drawer_enabled = models.BooleanField(default=False)
    auto_print_receipt = models.BooleanField(default=True)
    default_payment_method = models.CharField(max_length=50, default='cash')
    tax_inclusive_pricing = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'pos_settings'

    def __str__(self):
        return f"POS Settings - {self.organization.name}"
