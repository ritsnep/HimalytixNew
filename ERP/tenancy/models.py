from django.db import models
import uuid

from django.db import models


class Tenant(models.Model):
    tenant_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=100, unique=True)
    subscription_tier = models.CharField(max_length=50, default='standard')
    is_active = models.BooleanField(default=True)
    domain_name = models.CharField(max_length=255, unique=True, null=True, blank=True)
    data_schema = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.code})"

    class Meta:
        db_table = "tenants"


class SubscriptionPlan(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    base_price = models.DecimalField(max_digits=12, decimal_places=2)
    billing_cycle = models.CharField(max_length=20, default='monthly')
    max_users = models.IntegerField()
    max_storage_gb = models.IntegerField()
    features = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "subscription_plans"


class TenantSubscription(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    auto_renew = models.BooleanField(default=True)
    status = models.CharField(max_length=50, default='active')
    billing_cycle = models.CharField(max_length=20, default='monthly')
    price_per_period = models.DecimalField(max_digits=12, decimal_places=2)
    currency_code = models.CharField(max_length=3, default='USD')
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    next_billing_date = models.DateField()
    last_billing_date = models.DateField(null=True, blank=True)
    payment_method_id = models.IntegerField(null=True, blank=True)
    cancellation_date = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.tenant.code} - {self.plan.code}"

    class Meta:
        db_table = "tenant_subscriptions"


class TenantConfig(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    config_key = models.CharField(max_length=100)
    config_value = models.TextField(null=True, blank=True)
    data_type = models.CharField(max_length=50, default="string")

    def __str__(self):
        return f"{self.tenant.code} - {self.config_key}"

    class Meta:
        db_table = "tenant_config"
        unique_together = ('tenant', 'config_key')


