# Printing app

Provides per-user print template configuration and print pages for journals.

## URLs

- Print configuration (per-user): `/print/settings/`
- Preview (configurable): `/print/preview/<journal_id>/`
- Print (auto opens print dialog): `/print/<journal_id>/`

URL names:

- `print_settings`
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

## Sidebar entry

The left sidebar includes **Print Configuration** under Accounting:

- `ERP/templates/partials/left-sidebar.html`

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

## How to test manually

1. Start the server (from repo root):
   - VS Code task: `Run Django server (venv python)`

2. Open a real journal detail page:
   - `/accounting/journals/<id>/`

3. Use the buttons:
   - **Print Preview** opens `/print/preview/<id>/` in a new tab.
   - **Print** opens `/print/<id>/` in a new tab and triggers the browser print dialog.

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

## Tests

Run app tests from `ERP/`:

- `python manage.py test printing`
