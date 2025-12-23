# Voucher Config App

This Django app provides a configuration-driven voucher entry UI and CRUD operations for the ERP system. It enables dynamic voucher forms based on database-stored configurations, supporting multiple voucher types across accounting, sales, purchasing, and inventory modules.

## Architecture

The app is designed to be isolated from the existing accounting module while integrating with its services for posting and validation. It uses HTMX for dynamic UI updates without page reloads.

### Core Models

- **VoucherConfigMaster**: Defines voucher type metadata, labels, flags, and schema overrides
- **InventoryLineConfig**: Configures line item grid columns and behaviors for inventory vouchers
- **FooterChargeSetup**: Defines footer charges, taxes, and totals calculations
- **VoucherUDFConfig**: Manages user-defined fields for custom voucher extensions

### Key Components

- **Schema Builder**: `resolve_ui_schema()` method generates UI schemas from configurations
- **HTMX Views**: Dynamic endpoints for form interactions (add lines, validate, save draft, post)
- **Draft Service**: Atomic draft saves with rollback capabilities
- **Posting Orchestrator**: Integrates with existing accounting posting workflow
- **Form Factory Integration**: Uses existing `VoucherFormFactory` for form generation

## Workflows

### Voucher Entry Process
1. **Select Voucher Type**: Choose from available configurations
2. **Enter Header Data**: Dynamic form based on config
3. **Add Line Items**: HTMX-powered grid with configurable columns
4. **Apply Charges**: Footer charges and totals calculation
5. **Save Draft**: Atomic save with validation
6. **Post Voucher**: Triggers accounting posting workflow

### CRUD Operations
- Create: New voucher instances via config-driven forms
- Read: Display vouchers with dynamic layouts
- Update: Edit drafts with real-time validation
- Delete: Remove unposted vouchers

## Endpoints

- `/voucher-config/select/`: Voucher type selection
- `/voucher-config/new/<code>/`: Create new voucher
- `/voucher-config/edit/<id>/`: Edit existing voucher
- `/voucher-config/draft/<id>/`: Save draft via HTMX
- `/voucher-config/post/<id>/`: Post voucher
- `/voucher-config/add-line/`: Add line item via HTMX
- `/voucher-config/validate/`: Real-time validation

## Configuration

### Seeding
Run `python manage.py seed_voucher_configs` to populate baseline configurations.

### Schema Definition
Configurations use JSON schemas for UI generation:
```json
{
  "header": {
    "fields": [
      {"name": "voucher_date", "type": "date", "required": true},
      {"name": "customer", "type": "select", "lookup": "customer"}
    ]
  },
  "lines": {
    "fields": [
      {"name": "item", "type": "select", "lookup": "inventory_item"},
      {"name": "quantity", "type": "number", "decimal_places": 2}
    ]
  }
}
```

## Integration

### With Accounting Module
- Uses `VoucherFormFactory` for form generation
- Integrates with posting services via `PostingOrchestrator`
- Shares audit logging and validation rules
- Maintains 1:1 voucher-to-journal mapping

### Dependencies
- Django 4.2+
- HTMX for dynamic UI
- Existing accounting models and services

## Testing

Run tests with `python manage.py test voucher_config`

### Test Coverage
- Model validation and schema resolution
- HTMX endpoint responses
- Draft save atomicity
- Posting workflow integration
- Form validation and error handling

## Troubleshooting

### Common Issues
- **Schema Resolution Errors**: Check `schema_definition` JSON validity
- **Posting Failures**: Verify accounting service integration
- **HTMX Not Updating**: Check endpoint URLs and response formats
- **Validation Errors**: Review configuration flags and field definitions

### Debug Commands
- `python manage.py check_voucher_schemas`: Validate all configurations
- `python manage.py list_voucher_configs`: Display active configurations
- `python manage.py test_posting_workflow`: Test integration with accounting

## Deployment

See `DEPLOYMENT.md` for production rollout checklist and procedures.

## UI Guidelines

Front-end conventions, reusable widgets and HTMX/Alpine patterns are documented in `UI_GUIDELINES.md`.
Follow the `form_base.html` and `list_base.html` contracts when building voucher forms and lists.