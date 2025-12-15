"""
NEPALI DATE FIELD INTEGRATION GUIDE
====================================

This document outlines how to integrate dynamic Nepali date field support
across all schemas in the Himalytix ERP system.

## Overview

The `utils/date_field_utils.py` module provides schema-aware utilities for
automatically configuring date fields with dual calendar (AD/BS) support
across accounting, inventory, and service management modules.

## Key Features

1. **Automatic Date Field Discovery**: Identifies date fields across all models
2. **Widget Configuration**: Automatically applies DualCalendarWidget to date fields
3. **Schema-Based Configuration**: Uses SCHEMA_DATE_FIELDS for fine-grained control
4. **Organization-Aware**: Respects organization calendar preferences
5. **Exclude Patterns**: Automatically excludes audit/timestamp fields

## Configuration

### Schema Definition (date_field_utils.py)

The `SCHEMA_DATE_FIELDS` dictionary maps model names to their date fields:

```python
SCHEMA_DATE_FIELDS = {
    "FiscalYear": ["start_date", "end_date"],
    "PurchaseInvoice": ["invoice_date", "due_date", "delivery_date"],
    "Product": ["manufacture_date", "expiry_date"],
    "ServiceContract": ["start_date", "end_date", "renewal_date"],
    ...
}
```

### Adding New Models

To add Nepali date support to a new model:

1. Add to SCHEMA_DATE_FIELDS:
```python
SCHEMA_DATE_FIELDS["MyModel"] = ["date_field1", "date_field2"]
```

Or use the runtime registration function:
```python
from utils.date_field_utils import register_date_field_schema
register_date_field_schema("MyModel", ["date_field1", "date_field2"])
```

## Usage

### 1. Apply to Forms (Class-Based)

```python
from utils.date_field_utils import apply_date_widgets_to_form

class FiscalYearForm(forms.ModelForm):
    class Meta:
        model = FiscalYear
        fields = ['code', 'name', 'start_date', 'end_date']

# Apply date widgets
FiscalYearForm = apply_date_widgets_to_form(FiscalYearForm, organization=org)
```

### 2. Configure Forms (Instance-Based)

```python
from utils.date_field_utils import configure_form_date_fields

def my_view(request):
    form = FiscalYearForm()
    configure_form_date_fields(form, organization=request.user.organization)
    # Form now has proper date initialization
    ...
```

### 3. Batch Configuration

```python
from utils.date_field_utils import batch_configure_forms

forms_list = [FiscalYearForm, JournalForm, PurchaseInvoiceForm]
configured_forms = batch_configure_forms(forms_list, organization=org)
```

### 4. Get Date Fields for a Model

```python
from utils.date_field_utils import get_date_fields_for_model

date_fields = get_date_fields_for_model(FiscalYear)
# Returns: [('start_date', <DateField>), ('end_date', <DateField>)]
```

## Widget Behavior

The `DualCalendarWidget` provides:

1. **Dual Input Fields**: AD and BS date inputs
2. **Two-Way Conversion**: Automatic conversion between calendars
3. **Toggle Button**: Users can switch between AD and BS views
4. **Nepali Datepicker**: Interactive calendar picker (JS library)
5. **Fallback Support**: Works gracefully if JS assets unavailable

### Widget Configuration Options

```python
from utils.widgets import dual_date_widget

# Create widget with specific settings
widget = dual_date_widget(
    attrs={"class": "custom-date", "data-theme": "dark"},
    organization=org,
    default_view="BS"  # AD, BS, or DUAL
)
```

## Supported Models by Module

### Accounting Module
- FiscalYear (start_date, end_date)
- AccountingPeriod (start_date, end_date)
- Journal (posting_date)
- JournalLine (posting_date)
- ChartOfAccount (effective_from, effective_to)
- GeneralLedger (posting_date, transaction_date)
- PurchaseInvoice (invoice_date, due_date, delivery_date)
- SalesInvoice (invoice_date, due_date, delivery_date)
- SalesOrder (order_date, due_date)
- And 20+ more...

### Inventory Module
- Product (manufacture_date, expiry_date)
- Batch (manufacture_date, expiry_date)
- StockLedger (txn_date)
- PriceList (valid_from, valid_to)
- Shipment (estimated_delivery, actual_delivery)

### Service Management Module
- ServiceContract (start_date, end_date, renewal_date)
- ServiceTicket (assigned_date, created_date, closed_date)
- DeviceLifecycle (deployed_date)
- And more...

## Integration Examples

### Example 1: Auto-Configure a Journal Form

```python
from accounting.forms import JournalForm
from utils.date_field_utils import apply_date_widgets_to_form

# In forms.py or views.py
JournalFormWithDualCalendar = apply_date_widgets_to_form(
    JournalForm,
    organization=request.user.organization
)

# Use in view
form = JournalFormWithDualCalendar()
```

### Example 2: Custom Widget in Template

```html
<!-- The widget handles rendering both inputs -->
{{ form.posting_date }}

<!-- Results in:
  <div class="dual-calendar-widget">
    <input type="date" id="id_posting_date" name="posting_date" class="form-control dual-calendar__ad" />
    <input type="date" id="id_posting_date_bs" name="posting_date_bs" class="form-control dual-calendar__bs" />
    <button type="button" class="btn-toggle">⇄</button>
  </div>
-->
```

### Example 3: Display Nepali Dates

```python
from utils.date_field_utils import get_date_field_display_value
from utils.calendars import CalendarMode

# Display in AD (default)
date_str = get_date_field_display_value(datetime.date(2025, 12, 15))
# Result: "2025-12-15"

# Display in BS
date_str = get_date_field_display_value(
    datetime.date(2025, 12, 15),
    calendar_mode=CalendarMode.BS
)
# Result: "2082-08-30"

# Display both
date_str = get_date_field_display_value(
    datetime.date(2025, 12, 15),
    calendar_mode=CalendarMode.DUAL,
    include_both=True
)
# Result: "2025-12-15 (BS: 2082-08-30)"
```

## Testing

Run the comprehensive test suite:

```bash
# Test date field discovery
pytest tests/test_date_field_utils.py::DateFieldUtilsTestCase -v

# Test widget application
pytest tests/test_date_field_utils.py::WidgetApplicationTestCase -v

# Test schema registration
pytest tests/test_date_field_utils.py::SchemaRegistrationTestCase -v

# Test display formatting
pytest tests/test_date_field_utils.py::DateDisplayTestCase -v

# Run all tests
pytest tests/test_date_field_utils.py -v
```

## Calendar Mode Configuration

Each organization can have a preferred calendar mode set in its config:

```python
org.config.calendar_mode = "BS"  # BS, AD, or DUAL
org.config.calendar_date_seed = "LATEST"  # LATEST or TODAY
org.config.save()
```

This is automatically detected and applied to all date widgets for that org.

## Troubleshooting

### Issue: Nepali dates not showing in widgets

1. Check that `static/libs/nepali-datepicker/` files exist
2. Verify `nepali.datepicker` JS is loaded in templates
3. Check browser console for JS errors
4. Ensure `dual-calendar.js` is included in template

### Issue: Date conversion failing

1. Verify `nepali-datetime` package is installed
2. Check calendar conversion functions in `utils/calendars.py`
3. Use `maybe_coerce_bs_date()` for tolerant parsing

### Issue: Widget not applied to form

1. Ensure form class has `Meta.model` attribute
2. Check that `apply_date_widgets_to_form()` is called
3. Verify model is in `SCHEMA_DATE_FIELDS`
4. Use `configure_form_date_fields()` for instance configuration

## Performance Considerations

1. **Lazy Loading**: Widgets are created on-demand
2. **Caching**: Date field discovery is cached per model
3. **Batch Config**: Use `batch_configure_forms()` for multiple forms
4. **Schema Spec**: Explicit configuration is faster than auto-discovery

## Future Enhancements

1. **API Support**: JSON date serialization with calendar modes
2. **Bulk Import**: CSV/Excel import with date format detection
3. **Reporting**: Date range filters with calendar pickers
4. **Mobile**: Mobile-optimized calendar interface

## References

- `utils/date_field_utils.py` - Main utilities module
- `utils/widgets.py` - Widget implementations
- `utils/calendars.py` - Calendar conversion functions
- `tests/test_date_field_utils.py` - Comprehensive test suite
