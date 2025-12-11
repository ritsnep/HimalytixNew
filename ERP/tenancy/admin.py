from django import forms
from django.contrib import admin
from django.utils.html import format_html

from .models import (
	SubscriptionPlan,
	Tenant,
	TenantBrandingConfig,
	TenantConfig,
	TenantSubscription,
)

BRANDING_FAVICON_KEY = "branding.favicon_url"
BRANDING_BRAND_COLOR_KEY = "brand_color"


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
	config_type = forms.ChoiceField(
		label="Branding Setting",
		choices=[
			("favicon", "Favicon URL"),
			("brand_color", "Brand Color"),
		],
		initial="favicon",
		widget=forms.Select(attrs={"id": "branding-config-type"}),
	)
	
	config_value = forms.CharField(
		label="Value",
		help_text="Either a favicon URL or a hex color code",
		required=False,
		widget=forms.TextInput(attrs={"placeholder": "Enter value (URL or #RRGGBB)"}),
	)

	class Meta:
		model = TenantBrandingConfig
		fields = ("tenant", "config_value")
		widgets = {
			"tenant": forms.Select(attrs={"style": "width: 300px"}),
		}

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		# Determine which type this is based on existing config_key
		if self.instance and self.instance.pk:
			if self.instance.config_key == BRANDING_FAVICON_KEY:
				self.fields['config_type'].initial = 'favicon'
				self.fields['config_value'].label = "Favicon URL"
				self.fields['config_value'].help_text = "Absolute URL or /static/ path to the favicon. Leave blank to fall back to default."
			elif self.instance.config_key == BRANDING_BRAND_COLOR_KEY:
				self.fields['config_type'].initial = 'brand_color'
				self.fields['config_value'].label = "Brand Color"
				self.fields['config_value'].help_text = "Hex color code (e.g., #1c84ee)"
				self.fields['config_value'].widget = forms.TextInput(attrs={
					"type": "color",
					"placeholder": "#1c84ee",
					"style": "width: 100px; height: 40px;"
				})

	def clean(self):
		cleaned_data = super().clean()
		config_type = cleaned_data.get('config_type')
		config_value = cleaned_data.get('config_value', '').strip()
		
		if config_type == 'brand_color' and config_value:
			# Validate hex color
			if not config_value.startswith('#') or len(config_value) != 7:
				raise forms.ValidationError(
					"Brand color must be a valid hex color (e.g., #1c84ee)"
				)
			try:
				int(config_value[1:], 16)
			except ValueError:
				raise forms.ValidationError(
					"Brand color must be a valid hex color (e.g., #1c84ee)"
				)
		
		return cleaned_data

	def save(self, commit=True):
		instance = super().save(commit=False)
		config_type = self.cleaned_data.get('config_type')
		
		if config_type == 'favicon':
			instance.config_key = BRANDING_FAVICON_KEY
		elif config_type == 'brand_color':
			instance.config_key = BRANDING_BRAND_COLOR_KEY
		
		instance.data_type = "string"
		if commit:
			instance.save()
		return instance


@admin.register(TenantBrandingConfig)
class TenantBrandingConfigAdmin(admin.ModelAdmin):
	form = TenantBrandingConfigAdminForm
	list_display = ("tenant", "config_key_display", "value_preview")
	search_fields = ("tenant__name", "tenant__code")
	autocomplete_fields = ("tenant",)
	ordering = ("tenant__name", "config_key")

	def config_key_display(self, obj):
		"""Display a friendly name for the config key."""
		if obj.config_key == BRANDING_FAVICON_KEY:
			return "Favicon URL"
		elif obj.config_key == BRANDING_BRAND_COLOR_KEY:
			return "Brand Color"
		return obj.config_key

	config_key_display.short_description = "Setting"

	def value_preview(self, obj):
		"""Display a preview of the value."""
		if obj.config_key == BRANDING_BRAND_COLOR_KEY and obj.config_value:
			# Show a color swatch for brand colors
			return format_html(
				'<span style="display: inline-block; width: 20px; height: 20px; background-color: {}; border: 1px solid #ccc; border-radius: 3px; margin-right: 8px;"></span>{}',
				obj.config_value,
				obj.config_value
			)
		else:
			# Show truncated value for favicon URLs
			value = obj.config_value or ""
			return value[:60] + ("…" if len(value) > 60 else "")

	value_preview.short_description = "Value"

	def delete_model(self, request, obj):
		obj.delete()

