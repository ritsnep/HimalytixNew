# Voucher Entry — Architecture Parity with Journal Entry

This document explains the architectural parity between the new Voucher Entry UI and the existing Journal Entry UI. The goal: keep feature parity and reuse patterns, models, endpoints and UX behaviors from the proven Journal Entry implementation.

Key features copied / aligned

- Application bootstrap area (`#app`) — contains data attributes used by client-side JS to discover endpoints, defaults and flags. (See `voucher_entry_new.html`.)
- Debug console panel — identical behavior to `journal_entry.html`'s debug console; controlled by `journal_debug_enabled` / `voucher_debug_enabled` server flag.
- HTMX integration — uses the same patterns: `hx-post` to add rows, inline edits post to `/journal-entry/row/`, row duplication and deletion endpoints, and `account_lookup` endpoint for suggestions.
- Server-side HTMX handlers — reuse `journal_entry` handlers (in `accounting/views/views_journal_grid.py` and `accounting/views/journal_entry.py`) for add-row, row updates, duplicate, account-lookup.
- Voucher config model (`VoucherModeConfig`) — created/seeded using existing scripts and linked to JournalType (`GJ`). The UDF model (`VoucherUDFConfig`) is fully supported and has API endpoints present (`/forms_designer/api/udfs/`).
- Sticky bottom action bar — matches Dashboard / Journal entry UX and keeps actions visible at all times.
- Initial row behavior — auto-insert a blank row on first load to match Journal Entry behavior and reduce friction for frequent users.
- Permissions & redirects — follows the same permission checks (`('accounting','journal','add')`) and redirects to login when unauthorized.

Files to inspect / extend

- Templates
  - `accounting/templates/accounting/journal_entry.html` (reference)
  - `accounting/templates/accounting/voucher_entry_new.html` (current implementation)
  - `accounting/templates/accounting/htmx/voucher_entry_grid.html`
  - `accounting/templates/accounting/htmx/voucher_entry_grid_row.html`

- Views & Handlers
  - `accounting/views/views_journal_grid.py` (HTMX handlers, account lookup)
  - `accounting/views/journal_entry.py` (core journal entry views / helpers)
  - `accounting/views/voucher_crud_views.py` (voucher CRUD & initial state)

- Models
  - `accounting.models.VoucherModeConfig`
  - `accounting.models.VoucherUDFConfig`

Next recommended extensions

- Convert account select to an HTMX typeahead that reuses `journal_entry`'s `account_lookup` endpoint.
- Add keyboard navigation and fast entry features matching Journal Entry (tab/enter handling, arrow keys, quick duplicate).
- Add integration tests for add-row flow and UDF CRUD via API.

If you want, I can proceed to implement the account typeahead and keyboard navigation next — which would bring the Voucher Entry even closer to the Journal Entry UX.
