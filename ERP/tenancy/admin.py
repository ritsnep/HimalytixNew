from django.contrib import admin
from .models import Tenant, SubscriptionPlan, TenantSubscription, TenantConfig
from django.contrib import admin


admin.site.register(Tenant)
admin.site.register(SubscriptionPlan)
admin.site.register(TenantSubscription)
admin.site.register(TenantConfig)
