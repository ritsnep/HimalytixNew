# Universal Bulk Import and Template System

## Overview

This system provides a **single source of truth** backend-driven approach for bulk import and demo templates that works for ANY model in the system. Everything is dynamically rendered from backend configuration - no hardcoded templates or static data.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    BACKEND (Single Source)                   │
├─────────────────────────────────────────────────────────────┤
│  1. BulkImportMixin - Universal bulk import logic           │
│  2. DemoTemplateMixin - Universal template system           │
│  3. Field Configuration - Dynamic field metadata            │
│  4. Template Definitions - Backend-defined demo data        │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                 FRONTEND (Dynamic Rendering)                 │
├─────────────────────────────────────────────────────────────┤
│  1. Form template extends _coa_form_base.html               │
│  2. Bulk import tab renders from field_config               │
│  3. Templates tab renders from backend templates            │
│  4. All UI generated from backend metadata                  │
└─────────────────────────────────────────────────────────────┘
```

## Key Features

### ✅ Single Source of Truth
- All field configurations defined once in view class
- Template data defined in Python (can be loaded from DB/files)
- UI automatically generated from backend metadata
- No duplication between backend and frontend

### ✅ Type Safety
- Field type conversion (str, int, float, bool, decimal)
- Foreign key resolution
- Self-referential (parent) relationships
- Choice field validation

### ✅ Validation
- Required field checking
- Duplicate detection
- FK existence validation
- Custom validation hooks

### ✅ Error Handling
- Line-by-line error reporting
- Skip errors and continue option
- Preview before import
- Transaction safety

## Implementation Guide

### Step 1: Create Bulk Import View

```python
# accounting/views/my_model_bulk_import.py
from accounting.mixins.bulk_import_mixin import BulkImportMixin, DemoTemplateMixin
from accounting.models import MyModel

class MyModelBulkCreateView(BulkImportMixin, PermissionRequiredMixin, View):
    model = MyModel
    permission_required = ('accounting', 'mymodel', 'add')
    
    # Define fields in the order they appear in pasted data
    bulk_fields = ['code', 'name', 'parent_code', 'is_active']
    
    # Detailed field configuration
    bulk_field_config = {
        'code': {
            'required': True,
            'type': 'str',
            'unique_field': True,  # Check for duplicates
            'help_text': 'Unique identifier code',
        },
        'name': {
            'required': True,
            'type': 'str',
            'help_text': 'Display name',
        },
        'parent_code': {
            'required': False,
            'type': 'self',  # Self-referential FK
            'lookup': 'code',  # Which field to lookup
            'help_text': 'Parent item code (optional)',
        },
        'category': {
            'required': True,
            'type': 'fk',  # Foreign key
            'model': Category,
            'lookup': 'name',  # Lookup by name
            'help_text': 'Category name',
        },
        'status': {
            'required': False,
            'type': 'choice',
            'choices': MyModel.STATUS_CHOICES,
            'help_text': 'Status value',
        },
        'is_active': {
            'required': False,
            'type': 'bool',
            'help_text': 'Active status (true/false)',
        },
        'rate': {
            'required': False,
            'type': 'decimal',
            'help_text': 'Decimal rate value',
        },
    }
    
    def get_organization(self):
        return self.request.user.get_active_organization()
    
    # Optional: Custom validation
    def validate_custom(self, prepared_data, row_data):
        """Return list of error strings or empty list"""
        errors = []
        if prepared_data['rate'] < 0:
            errors.append('Rate cannot be negative')
        return errors
```

### Step 2: Create Demo Template View

```python
class MyModelDemoImportView(DemoTemplateMixin, PermissionRequiredMixin, View):
    model = MyModel
    permission_required = ('accounting', 'mymodel', 'add')
    
    # Define demo templates as dictionaries
    demo_templates = {
        'basic-setup': [
            {
                'code': 'ITEM001',
                'name': 'First Item',
                'category': 'General',  # Will be resolved to Category FK
                'is_active': True,
            },
            {
                'code': 'ITEM002',
                'name': 'Second Item',
                'category': 'General',
                '_parent_ref': 'ITEM001',  # Reference to parent by code
                'is_active': True,
            },
        ],
        'advanced-setup': [
            # More complex demo data
        ],
    }
    
    # Template metadata for better UI
    template_metadata = {
        'basic-setup': {
            'name': 'Basic Setup',
            'description': 'Minimal starter template with 2 items',
            'icon': 'bx-file',
        },
        'advanced-setup': {
            'name': 'Advanced Setup',
            'description': 'Complete template with hierarchical data',
            'icon': 'bx-sitemap',
        },
    }
    
    def get_organization(self):
        return self.request.user.get_active_organization()
    
    # Optional: Load templates from database
    def get_demo_templates(self):
        # Can load from DB, files, or API
        templates = {}
        template_records = DemoTemplate.objects.filter(model_name='mymodel')
        for record in template_records:
            templates[record.key] = record.data
        return templates
```

### Step 3: Add URL Patterns

```python
# accounting/urls.py
urlpatterns = [
    path('mymodels/bulk-import/', 
         MyModelBulkCreateView.as_view(), 
         name='mymodel_bulk_import'),
    path('mymodels/demo-import/', 
         MyModelDemoImportView.as_view(), 
         name='mymodel_demo_import'),
    path('mymodels/demo-preview/', 
         MyModelDemoImportView.as_view(), 
         name='mymodel_demo_preview'),
]
```

### Step 4: Enable in Settings

```python
# dashboard/settings.py
ADVANCED_FORM_FEATURES = {
    'accounting': {
        'mymodel': {
            'enable_tabs': True,
            'enable_bulk_import': True,
            'enable_templates': True,
            'enable_shortcuts': True,
            'enable_save_and_new': True,
        },
    },
}
```

### Step 5: Update Form Template

Your form template just needs to extend `_coa_form_base.html` and define the tab contents. The bulk import and template tabs are automatically rendered!

```django
{% extends 'accounting/_coa_form_base.html' %}
{% load static %}
{% load bulk_import_tags %}

{% block form_content %}
<div class="tab-content">
    <!-- Single Entry Tab -->
    <div class="tab-pane fade show active" id="single-entry" role="tabpanel">
        <form id="mymodel-form" method="post" novalidate>
            {% csrf_token %}
            <!-- Your form fields here -->
        </form>
    </div>

    <!-- Bulk Import Tab (Auto-rendered from field_config) -->
    {% if enable_bulk_import %}
    <div class="tab-pane fade" id="bulk-import" role="tabpanel">
        <!-- Field info automatically rendered -->
        <div class="alert alert-info">
            <h6>Bulk Import Fields:</h6>
            <div class="row">
                {% for field_name in view.bulk_fields %}
                    <div class="col-md-3">
                        {% render_bulk_field_info field_name view.bulk_field_config|dict_get:field_name %}
                    </div>
                {% endfor %}
            </div>
        </div>
        
        <!-- Bulk import form (auto-wired with HTMX) -->
        <form hx-post="{% url 'accounting:mymodel_bulk_import' %}" 
              hx-target="#bulk-import-results">
            {% csrf_token %}
            <textarea name="bulk_data" class="form-control font-monospace" rows="10"></textarea>
            <button type="submit" class="btn btn-primary mt-3">
                <i class="bx bx-upload"></i> Import
            </button>
        </form>
        <div id="bulk-import-results" class="mt-4"></div>
    </div>
    {% endif %}

    <!-- Templates Tab (Auto-rendered from backend templates) -->
    {% if enable_templates %}
    <div class="tab-pane fade" id="demo-data" role="tabpanel">
        <div class="row">
            {% for template_key, template_data in view.demo_templates.items %}
                <div class="col-md-4">
                    <div class="template-card">
                        <h6>{{ view.template_metadata|dict_get:template_key|dict_get:'name' }}</h6>
                        <p>{{ view.template_metadata|dict_get:template_key|dict_get:'description' }}</p>
                        <button hx-get="{% url 'accounting:mymodel_demo_preview' %}?template={{ template_key }}"
                                hx-target="#demo-preview">
                            Preview
                        </button>
                    </div>
                </div>
            {% endfor %}
        </div>
        <div id="demo-preview"></div>
    </div>
    {% endif %}
</div>
{% endblock %}
```

## Field Type Reference

### Basic Types
- `str`: String field (default)
- `int`: Integer field
- `float`: Float field
- `bool`: Boolean (true/false, yes/no, 1/0)
- `decimal`: Decimal field

### Relationship Types
- `fk`: Foreign key to another model
  - `model`: The related model class
  - `lookup`: Field name to lookup (default: 'name')
  
- `self`: Self-referential foreign key (parent)
  - `lookup`: Field name to lookup (default: 'code')

- `choice`: Choice field
  - `choices`: List of valid choices

### Field Configuration Options

```python
{
    'field_name': {
        'required': True/False,
        'type': 'str|int|float|bool|decimal|fk|self|choice',
        'unique_field': True/False,  # Check for duplicates
        'help_text': 'Description shown in UI',
        
        # For FK fields
        'model': RelatedModel,
        'lookup': 'field_name',
        
        # For choice fields
        'choices': MODEL.CHOICE_CONSTANTS,
    }
}
```

## Example Implementations

### 1. Currency (Completed)
- File: `accounting/views/currency_bulk_import.py`
- Template: `accounting/templates/accounting/currency_form_enhanced.html`
- Features: 3 templates (major, asian, all-common currencies)

### 2. Tax Type (Example)

```python
class TaxTypeBulkCreateView(BulkImportMixin, PermissionRequiredMixin, View):
    model = TaxType
    bulk_fields = ['code', 'name', 'rate', 'is_active']
    
    bulk_field_config = {
        'code': {
            'required': True,
            'type': 'str',
            'unique_field': True,
        },
        'name': {
            'required': True,
            'type': 'str',
        },
        'rate': {
            'required': True,
            'type': 'decimal',
            'help_text': 'Tax rate percentage (e.g., 18.00)',
        },
        'is_active': {
            'required': False,
            'type': 'bool',
        },
    }

class TaxTypeDemoImportView(DemoTemplateMixin, PermissionRequiredMixin, View):
    model = TaxType
    
    demo_templates = {
        'india-gst': [
            {'code': 'GST5', 'name': 'GST 5%', 'rate': 5.00, 'is_active': True},
            {'code': 'GST12', 'name': 'GST 12%', 'rate': 12.00, 'is_active': True},
            {'code': 'GST18', 'name': 'GST 18%', 'rate': 18.00, 'is_active': True},
            {'code': 'GST28', 'name': 'GST 28%', 'rate': 28.00, 'is_active': True},
        ],
        'us-sales-tax': [
            {'code': 'ST5', 'name': 'Sales Tax 5%', 'rate': 5.00, 'is_active': True},
            {'code': 'ST7', 'name': 'Sales Tax 7%', 'rate': 7.00, 'is_active': True},
        ],
    }
```

### 3. Department (Hierarchical Example)

```python
class DepartmentBulkCreateView(BulkImportMixin, PermissionRequiredMixin, View):
    model = Department
    bulk_fields = ['code', 'name', 'parent_code', 'head_name', 'is_active']
    
    bulk_field_config = {
        'code': {
            'required': True,
            'type': 'str',
            'unique_field': True,
        },
        'name': {
            'required': True,
            'type': 'str',
        },
        'parent_code': {
            'required': False,
            'type': 'self',  # Parent department
            'lookup': 'code',
        },
        'head_name': {
            'required': False,
            'type': 'str',
        },
        'is_active': {
            'required': False,
            'type': 'bool',
        },
    }

class DepartmentDemoImportView(DemoTemplateMixin, PermissionRequiredMixin, View):
    model = Department
    
    demo_templates = {
        'company-structure': [
            {'code': 'EXEC', 'name': 'Executive', 'head_name': 'CEO'},
            {'code': 'FIN', 'name': 'Finance', '_parent_ref': 'EXEC', 'head_name': 'CFO'},
            {'code': 'ACC', 'name': 'Accounting', '_parent_ref': 'FIN'},
            {'code': 'TAX', 'name': 'Taxation', '_parent_ref': 'FIN'},
            {'code': 'OPS', 'name': 'Operations', '_parent_ref': 'EXEC', 'head_name': 'COO'},
        ],
    }
```

## Benefits

### For Developers
1. **Write Once, Use Everywhere**: Define configuration in Python, UI auto-generates
2. **Type Safety**: Built-in type conversion and validation
3. **No Template Duplication**: Single template works for all models
4. **Easy Testing**: Just test the mixins, not individual implementations

### For Users
1. **Consistent UX**: Same interface across all modules
2. **Preview Before Import**: See what will be imported
3. **Error Feedback**: Clear line-by-line error messages
4. **Multiple Options**: Paste data OR use templates

### For Business
1. **Faster Development**: New models get bulk import in minutes
2. **Lower Maintenance**: One system to update, not dozens of views
3. **Better Quality**: Centralized validation and error handling
4. **Scalability**: Easy to add new models and templates

## Advanced Features

### Custom Validation

```python
class MyModelBulkCreateView(BulkImportMixin, View):
    # ...
    custom_validator_method = 'validate_custom'
    
    def validate_custom(self, prepared_data, row_data):
        errors = []
        # Custom business logic
        if prepared_data['amount'] > 1000000:
            errors.append('Amount exceeds maximum allowed')
        return errors
```

### Dynamic Templates from Database

```python
class MyModelDemoImportView(DemoTemplateMixin, View):
    model = MyModel
    
    def get_demo_templates(self):
        templates = {}
        for template in DemoTemplate.objects.filter(model='mymodel'):
            templates[template.key] = json.loads(template.data)
        return templates
```

### Complex FK Resolution

```python
def resolve_foreign_keys(self, record_data, organization):
    resolved = super().resolve_foreign_keys(record_data, organization)
    
    # Custom FK logic
    if 'account_number' in record_data:
        account = ChartOfAccount.objects.get(
            organization=organization,
            account_code=record_data['account_number']
        )
        resolved['account'] = account
        
    return resolved
```

## Migration Checklist

To add bulk import and templates to an existing model:

- [ ] Create `{model}_bulk_import.py` with BulkCreateView and DemoImportView
- [ ] Define `bulk_fields` list (field order for parsing)
- [ ] Define `bulk_field_config` dict (field metadata)
- [ ] Define `demo_templates` dict (template data)
- [ ] Define `template_metadata` dict (UI descriptions)
- [ ] Add URL patterns (bulk-import, demo-import, demo-preview)
- [ ] Enable in settings (`ADVANCED_FORM_FEATURES`)
- [ ] Update form template to extend `_coa_form_base.html`
- [ ] Add bulk import tab with field info rendering
- [ ] Add templates tab with template card rendering
- [ ] Test: paste data, validate, import
- [ ] Test: preview template, import template
- [ ] Test: error handling, duplicate detection

## Testing

```python
# Test bulk import
POST /accounting/currencies/bulk-import/
{
    'bulk_data': 'USD\tUS Dollar\t$\ttrue\nEUR\tEuro\t€\ttrue',
    'validate_only': 'on'
}

# Test template import
POST /accounting/currencies/demo-import/
{
    'template_type': 'major-currencies'
}

# Test template preview
GET /accounting/currencies/demo-preview/?template=major-currencies
```

## Performance Considerations

1. **Bulk Operations**: Uses `bulk_create()` where possible
2. **Transaction Safety**: All imports wrapped in `transaction.atomic()`
3. **Lazy Loading**: Templates loaded on-demand
4. **Caching**: Field configs cached in view class
5. **Validation**: Early validation before DB hits

## Security

1. **Permission Checks**: Required on all views
2. **Organization Isolation**: Auto-filtered by organization
3. **CSRF Protection**: All forms include CSRF tokens
4. **SQL Injection**: Uses ORM, no raw SQL
5. **XSS Protection**: Template escaping enabled

## Next Steps

1. ✅ **Completed**: Currency implementation
2. **In Progress**: Create implementations for all 17 accounting forms
3. **Future**: Extend to billing, inventory modules
4. **Future**: Add Excel file upload support
5. **Future**: Add export templates feature
6. **Future**: Add template versioning and sharing
