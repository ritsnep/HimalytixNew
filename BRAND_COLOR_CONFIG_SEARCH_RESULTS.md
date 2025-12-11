# Brand Color & Organization Configuration Search Results

## Summary

The workspace uses a **multi-level configuration approach** for organization branding and theme settings. There are **two primary systems**:

1. **Tenant-Level Branding Configuration** (Global/Multi-Tenant)
2. **Organization-Level Feature Configuration** (Per-Organization)

---

## 1. TENANT-LEVEL BRANDING CONFIGURATION

### Models File: `tenancy/models.py`

#### `TenantConfig` Model
```python
class TenantConfig(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    config_key = models.CharField(max_length=100)
    config_value = models.TextField(null=True, blank=True)
    data_type = models.CharField(max_length=50, default="string")

    class Meta:
        db_table = "tenant_config"
        unique_together = ('tenant', 'config_key')
```

**Purpose**: Store arbitrary key-value configuration for tenants (SaaS multi-tenant system)

#### `TenantBrandingConfig` Model (Proxy)
```python
class TenantBrandingConfig(TenantConfig):
    """Proxy model to expose branding config entries in admin."""
    class Meta:
        proxy = True
        verbose_name = "Tenant branding setting"
        verbose_name_plural = "Tenant branding settings"
```

**Purpose**: Specialized proxy model for managing branding-specific configuration entries via Django Admin

### Supported Branding Configuration Keys

**File**: `utils/branding.py`

```python
BRANDING_KEY_MAP = {
    "branding.favicon_url": "favicon_url",
    "branding.logo_light_url": "logo_light_url",
    "branding.logo_dark_url": "logo_dark_url",
    "branding.logo_symbol_url": "logo_symbol_url",
    "branding.theme_color": "theme_color",
}
```

### Branding Helper Functions

**File**: `utils/branding.py`

#### Default Branding Values
```python
def _default_branding() -> Dict[str, Any]:
    """Base branding values used as a fallback when nothing is configured."""
    return {
        "favicon_url": static("images/favicon.ico"),
        "logo_light_url": static("images/himalytix-sm.svg"),
        "logo_dark_url": static("images/himalytix-sm.svg"),
        "logo_symbol_url": static("images/himalytix-sm.svg"),
        "theme_color": "#1c84ee",  # <-- DEFAULT BRAND COLOR
    }
```

#### Retrieve Branding for Tenant
```python
def get_branding_for_tenant(tenant: Optional[Tenant] = None) -> Dict[str, Any]:
    """Return merged branding data for a tenant with safe defaults."""
    branding = _default_branding()
    if tenant is None:
        return branding

    configs = TenantConfig.objects.filter(
        tenant=tenant,
        config_key__in=BRANDING_KEY_MAP.keys(),
    ).values("config_key", "config_value", "data_type")

    for config in configs:
        dict_key = BRANDING_KEY_MAP[config["config_key"]]
        parsed_value = _cast_config_value(config["config_value"], config.get("data_type"))
        if parsed_value:
            branding[dict_key] = parsed_value
    return branding
```

#### Get Branding from Request
```python
def get_branding_from_request(request) -> Dict[str, Any]:
    """Convenience helper that derives branding for a Django request."""
    tenant = getattr(request, "tenant", None)
    return get_branding_for_tenant(tenant)
```

### Admin Interface: `tenancy/admin.py`

#### TenantBrandingConfigAdmin
```python
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
```

**Currently Exposed**: Only favicon configuration, but the system is extensible to support all keys in `BRANDING_KEY_MAP`

---

## 2. ORGANIZATION-LEVEL FEATURE CONFIGURATION

### Models File: `usermanagement/models.py`

#### `Organization` Model
```python
class Organization(models.Model):
    VERTICAL_CHOICES = [
        ("retailer", "Retailer"),
        ("depot", "Depot"),
        ("logistics", "Logistics"),
    ]

    parent_organization = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL)
    tenant = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True, blank=True, related_name='organizations')
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50)
    type = models.CharField(max_length=50)
    legal_name = models.CharField(max_length=200, null=True, blank=True)
    tax_id = models.CharField(max_length=50, null=True, blank=True)
    registration_number = models.CharField(max_length=50, null=True, blank=True)
    industry_code = models.CharField(max_length=20, null=True, blank=True)
    fiscal_year_start_month = models.SmallIntegerField(default=1)
    fiscal_year_start_day = models.SmallIntegerField(default=1)
    fiscal_year_start = models.DateField(null=True, blank=True)
    base_currency_code = models.ForeignKey(
        'accounting.Currency',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='base_currency_code',
        to_field='currency_code',
        related_name='organizations',
    )
    address = models.TextField(blank=True, default="")
    vertical_type = models.CharField(
        max_length=20,
        choices=VERTICAL_CHOICES,
        default="retailer",
        help_text="Operational vertical for feature toggles.",
    )
    status = models.CharField(max_length=20, default="active")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)
```

**Note**: No direct brand color storage, but uses `CompanyConfig` for feature toggles

#### `CompanyConfig` Model
```python
class CompanyConfig(models.Model):
    """Feature toggles per company/tenant."""

    company = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name="config")
    enable_noc_purchases = models.BooleanField(default=False)
    enable_dealer_management = models.BooleanField(default=True)
    enable_logistics = models.BooleanField(default=False)
    enable_advanced_inventory = models.BooleanField(default=False)
    enforce_credit_limit = models.BooleanField(default=True)
    credit_enforcement_mode = models.CharField(max_length=10, choices=[...])
    calendar_mode = models.CharField(max_length=10, choices=CalendarMode.choices(), ...)
    calendar_date_seed = models.CharField(max_length=20, choices=DateSeedStrategy.choices(), ...)
    invoice_template = models.CharField(
        max_length=20,
        choices=[("a4", "A4 (Full Page)"), ("thermal", "Thermal (80mm)")],
        default="a4",
        help_text="Choose the print layout used for sales invoices.",
    )
    invoice_logo_url = models.URLField(
        blank=True,
        default="",
        help_text="Optional logo URL for printed invoices.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

**Brand Color Related**:
- `invoice_logo_url`: Organization-specific logo for invoices
- No direct brand color field yet (could be added)

---

## 3. ADDITIONAL RELATED CONFIGURATIONS

### POS Settings Model: `pos/models.py`
```python
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
```

### Voucher Mode Configuration: `accounting/models.py`
```python
class VoucherModeConfig(models.Model):
    """Configuration for voucher entry layout and behavior per organization."""
    LAYOUT_CHOICES = [
        ('standard', 'Standard'),
        ('compact', 'Compact'),
        ('detailed', 'Detailed'),
    ]
    
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name='voucher_mode_configs', ...)
    layout_style = models.CharField(max_length=20, choices=LAYOUT_CHOICES, default='standard')
    show_account_balances = models.BooleanField(default=True)
    show_tax_details = models.BooleanField(default=True)
    show_dimensions = models.BooleanField(default=True)
    default_currency = models.CharField(max_length=3, default='USD')
    # ... other display options
```

---

## 4. DJANGO SETTINGS CONFIGURATION

### File: `dashboard/settings.py`

#### DRF-Spectacular API Documentation
```python
SPECTACULAR_SETTINGS = {
    'TITLE': 'Himalytix ERP API',
    'DESCRIPTION': 'Multi-tenant ERP system for Nepal market - RESTful API',
    'VERSION': '1.0.0',
    # ... schema configuration
}
```

#### Chart of Accounts Configuration
```python
COA_MAX_DEPTH = int(os.environ.get("COA_MAX_DEPTH", 10))
```

---

## 5. FRONTEND THEME/BRANDING REFERENCES

### CSS Files
- **Default Theme Color**: `#1c84ee` (defined in multiple places)
- **Theme Toggle**: `collected_static_files/js/theme-toggle.js`
- **Light/Dark Mode Support**: Data attributes like `data-layout-mode`, `data-topbar`

### Sidebar Color Options: `templates/partials/right-sidebar.html`
```html
<div class="form-check sidebar-setting">
    <input class="form-check-input" type="radio" name="sidebar-color"
        id="sidebar-color-brand" value="brand" data-setting="sidebar-color">
    <label class="form-check-label" for="sidebar-color-brand">Brand</label>
</div>
```

---

## 6. TEST COVERAGE

### File: `tests/test_branding.py`

Tests cover:
- Default branding without tenant
- Tenant-specific favicon preferences
- Empty config value handling
- Branding context in request objects

---

## RECOMMENDED EXTENSIONS FOR BRAND COLOR STORAGE

### Option 1: Extend `CompanyConfig` (Organization-specific)
Add a new field to store organization brand color:
```python
class CompanyConfig(models.Model):
    # ... existing fields ...
    brand_color_primary = models.CharField(
        max_length=7,  # hex color like #1c84ee
        default="#1c84ee",
        help_text="Primary brand color for this organization (hex format)"
    )
    brand_color_secondary = models.CharField(
        max_length=7,
        default="#ffffff",
        help_text="Secondary brand color for this organization"
    )
```

### Option 2: Extend `TenantConfig` (Tenant/Workspace-wide)
Store tenant brand colors in the existing key-value system:
```
branding.color_primary -> #1c84ee
branding.color_secondary -> #ffffff
branding.color_accent -> #ffcc00
```

Then update `BRANDING_KEY_MAP` in `utils/branding.py`:
```python
BRANDING_KEY_MAP = {
    "branding.favicon_url": "favicon_url",
    "branding.logo_light_url": "logo_light_url",
    "branding.logo_dark_url": "logo_dark_url",
    "branding.logo_symbol_url": "logo_symbol_url",
    "branding.theme_color": "theme_color",
    "branding.color_primary": "color_primary",      # NEW
    "branding.color_secondary": "color_secondary",  # NEW
}
```

---

## FILE SUMMARY TABLE

| File Path | Model/Purpose | Brand Color Related |
|-----------|---------------|-------------------|
| `tenancy/models.py` | `TenantConfig`, `TenantBrandingConfig` | ✅ YES - stores branding config per tenant |
| `usermanagement/models.py` | `Organization`, `CompanyConfig` | ⚠️ PARTIAL - logo URL only |
| `utils/branding.py` | Branding helpers & defaults | ✅ YES - default color `#1c84ee` |
| `tenancy/admin.py` | Admin interface for branding | ✅ YES - favicon editor |
| `accounting/models.py` | `VoucherModeConfig` | ❌ NO - layout only |
| `pos/models.py` | `POSSettings` | ❌ NO - printer/scanner settings |
| `dashboard/settings.py` | Django settings | ⚠️ PARTIAL - general config |
| `tests/test_branding.py` | Branding tests | ✅ YES - test coverage |
