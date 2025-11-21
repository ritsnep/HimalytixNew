from django import forms
from django.contrib import admin

from .models import (
	SubscriptionPlan,
	Tenant,
	TenantBrandingConfig,
	TenantConfig,
	TenantSubscription,
)

BRANDING_FAVICON_KEY = "branding.favicon_url"


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
	list_display = ("name", "code", "is_active", "subscription_tier")
	search_fields = ("name", "code", "slug", "domain_name")
	list_filter = ("is_active", "subscription_tier")
	ordering = ("name",)


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
	list_display = ("name", "code", "is_active", "billing_cycle", "base_price")
	search_fields = ("name", "code")
	list_filter = ("is_active", "billing_cycle")
	ordering = ("name",)


@admin.register(TenantSubscription)
class TenantSubscriptionAdmin(admin.ModelAdmin):
	list_display = ("tenant", "plan", "status", "start_date", "end_date")
	search_fields = ("tenant__name", "tenant__code", "plan__name", "plan__code")
	list_filter = ("status", "billing_cycle", "auto_renew")
	autocomplete_fields = ("tenant", "plan")
	ordering = ("-start_date",)


@admin.register(TenantConfig)
class TenantConfigAdmin(admin.ModelAdmin):
	list_display = ("tenant", "config_key", "short_value", "data_type")
	list_filter = ("config_key", "data_type")
	search_fields = ("tenant__name", "tenant__code", "config_key", "config_value")
	autocomplete_fields = ("tenant",)
	ordering = ("tenant__name", "config_key")

	def short_value(self, obj):
		value = obj.config_value or ""
		return value[:60] + ("…" if len(value) > 60 else "")

	short_value.short_description = "Value"


class TenantBrandingConfigAdminForm(forms.ModelForm):
	config_value = forms.CharField(
		label="Favicon URL",
		help_text=(
			"Absolute URL or /static/ path to the favicon. "
			"Leave blank to fall back to the default Himalytix icon."
		),
		required=False,
		widget=forms.TextInput(attrs={"placeholder": "/static/images/favicon.ico"}),
	)

	class Meta:
		model = TenantBrandingConfig
		fields = ("tenant", "config_value")
		widgets = {
			"tenant": forms.Select(attrs={"style": "width: 300px"}),
		}

	def save(self, commit=True):
		instance = super().save(commit=False)
		instance.config_key = BRANDING_FAVICON_KEY
		instance.data_type = "string"
		if commit:
			instance.save()
		return instance


@admin.register(TenantBrandingConfig)
class TenantBrandingConfigAdmin(admin.ModelAdmin):
	form = TenantBrandingConfigAdminForm
	list_display = ("tenant", "config_value")
	search_fields = ("tenant__name", "tenant__code")
	autocomplete_fields = ("tenant",)
	ordering = ("tenant__name",)

	def get_queryset(self, request):
		qs = super().get_queryset(request)
		return qs.filter(config_key=BRANDING_FAVICON_KEY)

	def delete_model(self, request, obj):
		obj.delete()

