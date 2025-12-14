# Printing app

Provides per-user print template configuration and print pages for journals.

## URLs

- Print configuration (per-user): `/print/settings/`
- Print templates management: `/print/templates/`
- Create template: `/print/templates/create/`
- Edit template: `/print/templates/<id>/edit/`
- Delete template: `/print/templates/<id>/delete/`
- Preview (configurable): `/print/preview/<document_type>/<doc_id>/`
- Print (auto opens print dialog): `/print/<document_type>/<doc_id>/`

URL names:

- `print_settings`
- `template_list`
- `template_create`
- `template_update`
- `template_delete`
- `print_preview`
- `print_page`

## Permissions

- `printing.can_edit_print_templates`
  - Shows the configuration controls in the preview page.
  - Allows saving the per-user print configuration (POST to preview).

Users without the permission can still view the preview and print pages, but cannot save changes.

Note: all users can save their own preferences from `/print/settings/`.

## Templates

- `printing/templates/printing/preview.html`: preview shell + config form (plain POST + auto-submit JS)
- `printing/templates/printing/print_page.html`: print wrapper (calls `window.print()` on load)
- `printing/templates/printing/journal_classic.html`: “classic/modern” print layout
- `printing/templates/printing/journal_compact.html`: compact print layout

Shared includes:

- `printing/templates/printing/_paged_print_css.html`: print CSS helpers (A4/A5, repeated table headers, paged-engine page counters)
- `printing/templates/printing/_running_header.html`: reusable running header block

## Sidebar entry

The left sidebar includes **Print Configuration** and **Print Templates** under Accounting:

- `ERP/templates/partials/left-sidebar.html`

## Master Templates

Users can create named templates for different document types, storing custom configurations.

- Model: `PrintTemplate` (`ERP/printing/models.py`)
- Admin: registered in `ERP/printing/admin.py`

Fields:

- `user`: Foreign key to User
- `organization`: Foreign key to Organization (multi-tenant)
- `document_type`: Choices for document types ('journal', 'purchase_order', 'sales_order', 'sales_invoice')
- `name`: User-defined template name
- `paper_size`: 'A4' or 'A5'
- `config`: JSONField with toggles and template_name

### Template Selection Logic

When printing a document:

- If 1 master template exists for the document type: auto-select and print dialog opens immediately
- If multiple master templates exist: dropdown appears for user to select which template to use
- If no master templates: fall back to legacy individual template/paper selection

### Supported Document Types

- `journal`: Journal entries
- `purchase_order`: Purchase orders
- `sales_order`: Sales orders  
- `sales_invoice`: Sales invoices

### Template Files

Templates follow the pattern `printing/{document_type}_{template_name}.html`:

- `printing/journal_classic.html`
- `printing/journal_compact.html`
- `printing/purchase_order_classic.html`
- `printing/purchase_order_compact.html`
- `printing/sales_order_classic.html`
- `printing/sales_order_compact.html`
- `printing/sales_invoice_classic.html`
- `printing/sales_invoice_compact.html`

## Config toggles

Stored per-user in `PrintTemplateConfig.config` and merged with defaults in `printing/utils.py`.

Current toggle keys:

- `show_description`
- `show_department`
- `show_project`
- `show_cost_center`
- `show_tax_column`
- `show_audit`
- `show_signatures`
- `show_imbalance`

Options:

- `paper_size` (`A4` or `A5`)

## Audit trail

Print preference changes are written to the DB audit table:

- Model: `PrintSettingsAuditLog` (`ERP/printing/models_audit.py`)
- Admin: registered in `ERP/printing/admin.py`

Actions:

- `settings_update` (from `/print/settings/`)
- `preview_update` (from POST on `/print/preview/<journal_id>/` for users with permission)

## Organization scoping (multi-tenant safety)

Printing enforces same-organization access when the `Journal` has an `organization_id`.
If the journal does not have `organization_id` (e.g., dummy objects in unit tests), the guard is skipped.

Superusers bypass the org check.

## Migrations

This app includes migrations:

- `0001_initial.py`: `PrintTemplateConfig`
- `0002_printsettingsauditlog.py`: `PrintSettingsAuditLog`
- `0003_stable_audit_index_names.py`: stabilizes audit index names to avoid Django auto-generating rename migrations
- `0004_printtemplate.py`: `PrintTemplate` for master templates

Apply migrations from `ERP/`:

```powershell
python manage.py migrate printing
```

## Print Templates UI

Users can manage their print templates through a web interface:

- **Template List** (`/print/templates/`): View all user templates, create new, edit, delete
- **Create/Edit Template**: Form with document type, name, paper size, template style, and display toggles
- **Delete Template**: Confirmation page for safe deletion

Templates are scoped to user and organization for multi-tenancy.

## How to test manually

1. Start the server (from repo root):
   - VS Code task: `Run Django server (venv python)`

2. Access template management:
   - Go to `/print/templates/` or use the "Print Templates" link in the left sidebar
   - Create a new template with name, document type, paper size, and options
   - Edit or delete templates as needed

3. Test print flow:
   - Open a real journal detail page: `/accounting/journals/<id>/`
   - Use the **Print** button - it should auto-print if you have 1 journal template, or show selection if multiple
   - **Print Preview** opens `/print/preview/<id>/` in a new tab.

4. If you want to change and persist template/toggles:
   - Go to `/print/settings/` (also available in the left sidebar).
   - For users with permission `printing.can_edit_print_templates`, the preview page also shows inline controls.

## Adding new templates (developer guide)

This app renders the print body template via a safe include path:

- `template_path = "printing/journal_<template_name>.html"`
- root wrapper class: `template-<template_name>`

To add a new template (example key: `minimal`):

1. Create the HTML template file:
   - `ERP/printing/templates/printing/journal_minimal.html`

2. Register it in the template list:
   - Edit `ERP/printing/utils.py` and add to `TEMPLATE_CHOICES`:
     - `( "minimal", "Journal Voucher – Minimal" )`

3. (Optional but recommended) update the model choices for admin consistency:
   - `ERP/printing/models.py` → `template_name.choices`

4. Restart the server.

Notes:

- No migration is required for adding/removing template choices.
- Keep the template filename format `journal_<key>.html` to match the include logic.
- If you add a very different layout, you can scope CSS under `.template-<key> ...`.

## Seed command

To populate the system with default print templates and per-user print configuration for onboarding, use the management command:

```powershell
python manage.py load_printing_seed
```

Options:
- `--username <username>`: create seeds for a specific user instead of all superusers.
- `--org-id <id>`: optional organization id to attach templates to.
- `--force`: overwrite existing templates and configs for the target user(s).

The command creates one `PrintTemplate` per document type and allowed template style (classic/compact) and ensures a `PrintTemplateConfig` exists for the seeded user(s).

## Tests

Run app tests from `ERP/`:

- `python manage.py test printing`
