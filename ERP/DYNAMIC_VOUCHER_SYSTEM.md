# Dynamic Voucher System Documentation

## Overview

The Dynamic Voucher System provides a configuration-driven approach to creating and managing voucher forms across different modules (Accounting, Purchasing, Sales, Inventory). This system allows for flexible form generation based on JSON schemas stored in `VoucherConfiguration` models.

## Architecture

### Core Components

1. **VoucherConfiguration Model**: Stores form schemas, UI configurations, and metadata
2. **VoucherFormFactory**: Factory class for creating forms and formsets
3. **Dynamic Form Builder**: Schema-based form generation in `forms_factory.py`

### Key Features

- **Module-based Model Mapping**: Automatic mapping of configurations to appropriate Django models
- **Schema-driven Forms**: Forms generated from JSON schemas in `ui_schema` field
- **Multiple Configuration Support**: Handles multiple configurations per (module, code) pair
- **Fallback Mechanisms**: Graceful fallbacks for unknown configurations

## Model Mappings

### Header Models

| Module | Code | Header Model | Line Model |
|--------|------|--------------|------------|
| accounting | * | Journal | JournalLine |
| purchasing | purchase_order | PurchaseOrderVoucher | PurchaseOrderVoucherLine |
| purchasing | purchase_return | PurchaseReturnVoucher | PurchaseReturnVoucherLine |
| sales | sales_order | SalesOrderVoucher | SalesOrderVoucherLine |
| inventory | * | Journal | JournalLine |
| * | * | Journal | JournalLine (fallback) |

## Usage

### Creating Forms

```python
from accounting.forms.form_factory import VoucherFormFactory
from accounting.models import VoucherConfiguration

# Get configuration
config = VoucherConfiguration.objects.get(module='purchasing', code='purchase_return')

# Create form
form = VoucherFormFactory.get_generic_voucher_form(config, organization)

# Create formset
formset = VoucherFormFactory.get_generic_voucher_formset(config, organization)
```

### Form Schema Structure

The `ui_schema` field in VoucherConfiguration contains:

```json
{
  "header": [
    {
      "name": "supplier",
      "type": "select",
      "label": "Supplier",
      "choices": "Vendor",
      "required": true
    },
    {
      "name": "narration",
      "type": "textarea",
      "label": "Narration",
      "required": false
    }
  ],
  "lines": [
    {
      "name": "item",
      "type": "select",
      "label": "Item",
      "choices": "Item",
      "required": true
    },
    {
      "name": "quantity",
      "type": "number",
      "label": "Quantity",
      "required": true
    }
  ]
}
```

### Field Types Supported

- `text`: CharField with TextInput
- `textarea`: TextField with Textarea
- `number`: DecimalField with NumberInput
- `date`: DateField with DateInput
- `select`: ModelChoiceField with Select (supports model references)
- `checkbox`: BooleanField with CheckboxInput

## API Reference

### VoucherFormFactory Methods

#### `get_generic_voucher_form(voucher_config, organization, **kwargs)`

Creates a ModelForm for the voucher header.

**Parameters:**
- `voucher_config`: VoucherConfiguration instance
- `organization`: Organization instance
- `**kwargs`: Additional form kwargs (instance, data, files, etc.)

**Returns:** ModelForm class configured for the voucher type

#### `get_generic_voucher_formset(voucher_config, organization, **kwargs)`

Creates a FormSet for voucher lines.

**Parameters:**
- `voucher_config`: VoucherConfiguration instance
- `organization`: Organization instance
- `**kwargs`: Additional formset kwargs (instance, data, files, etc.)

**Returns:** FormSet class configured for the voucher type

#### `_get_model_for_voucher_config(voucher_config)`

Gets the appropriate Django model for a configuration.

**Parameters:**
- `voucher_config`: VoucherConfiguration instance

**Returns:** Django Model class

#### `_get_line_model_for_voucher_config(voucher_config)`

Gets the appropriate line Django model for a configuration.

**Parameters:**
- `voucher_config`: VoucherConfiguration instance

**Returns:** Django Model class

## Testing

Run the test suite:

```bash
python manage.py test accounting.tests.test_dynamic_vouchers
```

### Test Coverage

- Model mappings for all supported modules
- Form creation and validation
- Formset creation and validation
- Schema field validation
- Duplicate configuration handling
- Fallback mechanisms
- Integration workflows

## Configuration Management

### Creating New Voucher Configurations

1. Create VoucherConfiguration instance
2. Define `ui_schema` with header and lines schemas
3. Set appropriate module and code
4. The system will automatically map to correct models

### Adding New Modules

1. Update model mapping logic in `VoucherFormFactory._get_model_for_voucher_config()`
2. Update line model mapping in `VoucherFormFactory._get_line_model_for_voucher_config()`
3. Add corresponding test cases

### Schema Validation

Form schemas are validated at runtime. Invalid schemas may cause form creation failures.

## Troubleshooting

### Common Issues

1. **UnboundLocalError**: Check that `from django.apps import apps` is imported at method start
2. **FieldError**: Verify model has `is_active` field or update forms_factory.py
3. **LookupError**: Check that referenced models exist in the app registry
4. **KeyError**: Verify `ui_schema` contains 'header' and 'lines' keys

### Debug Steps

1. Check VoucherConfiguration exists and has valid ui_schema
2. Verify model mappings return correct Django models
3. Test form creation with minimal schema
4. Check Django debug logs for detailed errors

## Future Enhancements

- **Custom Field Types**: Extend schema support for custom widgets
- **Validation Rules**: Schema-based validation rules
- **Conditional Fields**: Show/hide fields based on other field values
- **Bulk Operations**: Support for bulk voucher creation
- **Template System**: Reusable form templates
- **Audit Trail**: Track configuration changes
- **Performance**: Caching for frequently used configurations