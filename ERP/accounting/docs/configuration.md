# Voucher Entry — Configuration & Dependencies

This document lists configuration, dependencies, and required files for the HTMX-based voucher entry grid.

Required Django version & Python
- Tested with: Django 4.2.x, Python 3.11+ (project uses Python 3.13 local env in CI/dev logs)

Front-end libraries
- HTMX 1.9.10 (the project typically includes HTMX via its global assets)
- HTMX WebSocket extension (optional)
- Bootstrap (the project's `dason` admin theme uses Bootstrap styles; Phase 1 UI has been converted to use Bootstrap classes)
- xlsx (for import/export features): `https://cdn.jsdelivr.net/npm/xlsx/dist/xlsx.full.min.js`

Important project files (Phase 1)
- Template: `accounting/templates/accounting/voucher_entry_new.html` — main page template
- Templates (HTMX partials):
  - `accounting/templates/accounting/htmx/voucher_entry_grid.html`
  - `accounting/templates/accounting/htmx/voucher_entry_grid_row.html`
- Server handlers:
  - `accounting/views/views_journal_grid.py` — contains `journal_entry_add_row`, `journal_entry_row`, and `journal_entry_row_duplicate` handlers used by HTMX
- Template tags:
  - `accounting/templatetags/voucher_tags.py` — `total_debit` and `total_credit` filters for totals
- Partials for account lookup:
  - `accounting/templates/accounting/partials/account_select_options.html`
  - `accounting/templates/accounting/partials/account_lookup_options.html`

Settings & permissions
- Ensure user has `('accounting', 'journal', 'add')` permission to access the voucher create page.
- The page will redirect to login if the user lacks permission or is unauthenticated.

Dev-time helpers
- An HTMX debug snippet was added to `voucher_entry_new.html` to log `htmx:afterRequest`, `htmx:afterSwap`, and show a small visual flash on swap. Remove before production if undesired.

Notes
- For large charts of accounts, replace the static select in row partial with a typeahead search using the `account_lookup` endpoint (already present in `views_journal_grid.py`).
- The server currently returns simple HTML fragments and minimal persistence (Phase 1 keeps line changes in memory; Phase 2 will implement persistence and validation).
- The UI now uses the project's `dason`/Bootstrap styles instead of Tailwind so it integrates visually with the admin template.
