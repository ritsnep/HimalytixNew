from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from usermanagement.models import CustomUser, Organization
# billing/models/subscription.py
"""
Subscription billing models for SaaS vertical playbook
Supports recurring billing, usage-based billing, milestone revenue recognition, and deferred revenue
"""
from decimal import Decimal, ROUND_HALF_UP
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from usermanagement.models import Organization
from accounting.models import ChartOfAccount


def quantize_amount(value: Decimal) -> Decimal:
    """Consistent monetary rounding (2dp)"""
    return (value or Decimal("0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class SubscriptionPlan(models.Model):
    """Subscription plan definition (pricing tiers, features)"""
    BILLING_CYCLES = [
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semi_annual', 'Semi-Annual'),
        ('annual', 'Annual'),
        ('one_time', 'One-Time'),
    ]
    
    PLAN_TYPES = [
        ('recurring', 'Recurring'),
        ('usage_based', 'Usage-Based'),
        ('tiered', 'Tiered Usage'),
        ('hybrid', 'Hybrid (Recurring + Usage)'),
    ]
    
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name='subscription_plans')
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPES, default='recurring')
    billing_cycle = models.CharField(max_length=20, choices=BILLING_CYCLES, default='monthly')
    base_price = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    currency_code = models.CharField(max_length=3, default='USD')
    
    # Revenue recognition
    revenue_account = models.ForeignKey(
        ChartOfAccount,
        on_delete=models.PROTECT,
        related_name='subscription_revenue_plans',
        null=True,
        blank=True
    )
    deferred_revenue_account = models.ForeignKey(
        ChartOfAccount,
        on_delete=models.PROTECT,
        related_name='deferred_revenue_plans',
        null=True,
        blank=True
    )
    
    # Trial and setup
    trial_period_days = models.IntegerField(default=0)
    setup_fee = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    
    # Contract terms
    minimum_commitment_months = models.IntegerField(default=0)
    auto_renew = models.BooleanField(default=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('organization', 'code')
        ordering = ['name']
    
    def __str__(self):
        return f"{self.organization.name} - {self.name} ({self.billing_cycle})"


class UsageTier(models.Model):
    """Usage tier pricing for tiered/usage-based plans"""
    subscription_plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE, related_name='usage_tiers')
    tier_name = models.CharField(max_length=100)
    min_quantity = models.DecimalField(max_digits=15, decimal_places=4)
    max_quantity = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    price_per_unit = models.DecimalField(max_digits=19, decimal_places=4)
    overage_price = models.DecimalField(max_digits=19, decimal_places=4, null=True, blank=True)
    
    class Meta:
        ordering = ['subscription_plan', 'min_quantity']
    
    def __str__(self):
        return f"{self.subscription_plan.name} - {self.tier_name}"


class Subscription(models.Model):
    """Customer subscription instance"""
    STATUS_CHOICES = [
        ('trial', 'Trial'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ]
    
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name='subscriptions')
    subscription_number = models.CharField(max_length=50, unique=True)
    customer_id = models.IntegerField()  # FK to Customer model
    subscription_plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name='subscriptions')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='trial')
    
    # Dates
    start_date = models.DateField()
    trial_end_date = models.DateField(null=True, blank=True)
    current_period_start = models.DateField()
    current_period_end = models.DateField()
    next_billing_date = models.DateField()
    cancellation_date = models.DateField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    
    # Pricing overrides
    custom_price = models.DecimalField(max_digits=19, decimal_places=4, null=True, blank=True)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Contract
    contract_term_months = models.IntegerField(null=True, blank=True)
    contract_end_date = models.DateField(null=True, blank=True)
    
    # Auto-renewal
    auto_renew = models.BooleanField(default=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['organization', 'customer_id', 'status']),
            models.Index(fields=['next_billing_date', 'status']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.subscription_number} - {self.subscription_plan.name}"
    
    @property
    def effective_price(self):
        """Calculate effective price after discounts"""
        base = self.custom_price if self.custom_price else self.subscription_plan.base_price
        discount = base * (self.discount_percent / Decimal('100'))
        return quantize_amount(base - discount)
    
    @property
    def is_in_trial(self):
        """Check if subscription is in trial period"""
        if self.status != 'trial':
            return False
        if self.trial_end_date and timezone.now().date() <= self.trial_end_date:
            return True
        return False


class SubscriptionUsage(models.Model):
    """Usage tracking for usage-based billing"""
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='usage_records')
    usage_date = models.DateField()
    usage_type = models.CharField(max_length=100)  # API calls, storage GB, users, etc.
    quantity = models.DecimalField(max_digits=15, decimal_places=4)
    unit_of_measure = models.CharField(max_length=50)
    
    # Calculated pricing
    tier_applied = models.ForeignKey(UsageTier, on_delete=models.SET_NULL, null=True, blank=True)
    calculated_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    
    # Billing status
    is_billed = models.BooleanField(default=False)
    billed_invoice_id = models.IntegerField(null=True, blank=True)
    
    recorded_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        indexes = [
            models.Index(fields=['subscription', 'usage_date', 'is_billed']),
        ]
        ordering = ['-usage_date']
    
    def __str__(self):
        return f"{self.subscription.subscription_number} - {self.usage_type}: {self.quantity} on {self.usage_date}"


class SubscriptionInvoice(models.Model):
    """Link subscriptions to invoices"""
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    subscription = models.ForeignKey(Subscription, on_delete=models.PROTECT, related_name='invoices')
    invoice_id = models.IntegerField()  # FK to InvoiceHeader
    invoice_number = models.CharField(max_length=50)
    
    billing_period_start = models.DateField()
    billing_period_end = models.DateField()
    
    # Amounts
    subscription_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    usage_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    setup_fee = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    total_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        indexes = [
            models.Index(fields=['organization', 'subscription']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.subscription.subscription_number} - Invoice {self.invoice_number}"


class DeferredRevenue(models.Model):
    """Deferred revenue schedule for ASC 606 compliance"""
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name='deferred_revenues')
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.PROTECT,
        related_name='deferred_revenues',
        null=True,
        blank=True
    )
    invoice_id = models.IntegerField(null=True, blank=True)  # FK to InvoiceHeader
    
    # Revenue recognition schedule
    contract_value = models.DecimalField(max_digits=19, decimal_places=4)
    deferred_amount = models.DecimalField(max_digits=19, decimal_places=4)
    recognized_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    
    # Period
    service_period_start = models.DateField()
    service_period_end = models.DateField()
    
    # Recognition method
    RECOGNITION_METHODS = [
        ('straight_line', 'Straight Line'),
        ('milestone', 'Milestone-Based'),
        ('usage', 'Usage-Based'),
        ('deliverable', 'Deliverable-Based'),
    ]
    recognition_method = models.CharField(max_length=20, choices=RECOGNITION_METHODS, default='straight_line')
    
    # Accounts
    deferred_revenue_account = models.ForeignKey(
        ChartOfAccount,
        on_delete=models.PROTECT,
        related_name='deferred_revenues',
    )
    revenue_account = models.ForeignKey(
        ChartOfAccount,
        on_delete=models.PROTECT,
        related_name='recognized_revenues',
    )
    
    is_fully_recognized = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['organization', 'is_fully_recognized']),
            models.Index(fields=['service_period_start', 'service_period_end']),
        ]
        ordering = ['service_period_start']
    
    def __str__(self):
        sub_num = self.subscription.subscription_number if self.subscription else 'N/A'
        return f"{sub_num} - Deferred: {self.deferred_amount}"
    
    @property
    def remaining_amount(self):
        """Calculate remaining deferred revenue"""
        return quantize_amount(self.deferred_amount - self.recognized_amount)


class DeferredRevenueSchedule(models.Model):
    """Monthly/periodic schedule for recognizing deferred revenue"""
    deferred_revenue = models.ForeignKey(
        DeferredRevenue,
        on_delete=models.CASCADE,
        related_name='schedule_lines'
    )
    recognition_date = models.DateField()
    recognition_amount = models.DecimalField(max_digits=19, decimal_places=4)
    
    is_recognized = models.BooleanField(default=False)
    journal_entry_id = models.IntegerField(null=True, blank=True)  # FK to Journal
    recognized_date = models.DateTimeField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['recognition_date']
    
    def __str__(self):
        return f"{self.deferred_revenue} - {self.recognition_date}: {self.recognition_amount}"


class MilestoneRevenue(models.Model):
    """Milestone-based revenue recognition for project/service contracts"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('invoiced', 'Invoiced'),
        ('recognized', 'Revenue Recognized'),
    ]
    
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    deferred_revenue = models.ForeignKey(
        DeferredRevenue,
        on_delete=models.CASCADE,
        related_name='milestones',
        null=True,
        blank=True
    )
    
    milestone_number = models.CharField(max_length=50)
    description = models.TextField()
    
    # Milestone details
    deliverable = models.CharField(max_length=200)
    due_date = models.DateField()
    completion_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Revenue
    milestone_value = models.DecimalField(max_digits=19, decimal_places=4)
    recognized_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    
    # Approval
    approved_by = models.IntegerField(null=True, blank=True)  # User ID
    approved_date = models.DateTimeField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('organization', 'milestone_number')
        ordering = ['due_date']
    
    def __str__(self):
        return f"{self.milestone_number} - {self.deliverable}"


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

    def refresh_totals_from_lines(self) -> None:
        """Recalculate aggregate amounts without breaking immutability safeguards."""
        if not self.pk:
            return
        actor = getattr(self, "_actor", None)
        self._allow_update = True
        if actor:
            self._actor = actor
        self.save(update_fields=["taxable_amount", "vat_amount", "total_amount", "updated_at"])

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
        if self.invoice_id:
            # Propagate totals to the parent invoice after every change to a line item.
            self.invoice.refresh_totals_from_lines()
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
