# Voucher Entry — HTMX Endpoints

This document lists HTMX endpoints and their behaviors for the voucher entry grid (Phase 1 implementation).

Note: many endpoints are intentionally shared with the legacy journal-entry UI (`journal_entry` handlers) and are located in `accounting/views/views_journal_grid.py` or `accounting/views/journal_entry.py`.

Primary endpoints

- `POST /accounting/journal-entry/add-row/` — `journal_entry_add_row`
  - Adds a new empty row and returns HTML fragment for the new row (renders `htmx/voucher_entry_grid_row.html`).
  - Expects: `line_count` param (current number of lines, used to number new row)
  - Returns: `HttpResponse` with HTML (status 200) or 500 on server error.

- `POST /accounting/journal-entry/row/` — `journal_entry_row`
  - Used for inline edits on a row. Current Phase 1 handler acknowledges the update and returns `OK`.
  - Expects: `field` (field name), `value` (new value), `line_id` (ID or index)
  - Returns: `HttpResponse("OK")` for now. In Phase 2 it will return updated fragment or validation errors.

- `POST /accounting/journal-entry/duplicate-row/` — `journal_entry_row_duplicate`
  - Duplicates a row and returns the duplicated row's HTML fragment.
  - Expects: `line_id` and optionally `line_count` to compute next index.

- `GET /accounting/journal-entry/row-template/` (not implemented here) — helper to fetch row template when needed.

Account lookup

- `GET /accounting/journal-entry/lookup/accounts/` — `account_lookup` in `views_journal_grid.py`
  - Accepts `q` query param for filtering by account code
  - Returns HTML fragment with either `<option>` elements (for HTMX-select) or a list of buttons (legacy dropdown)

Notes on HTMX usage
- HTMX `hx-post` calls target `#grid-rows` and mostly use `hx-swap="beforeend"` to append a new row.
- Inputs use `hx-post` on `blur` to send inline changes (e.g., description, debit/credit amounts).
- Ensure CSRF token is present on the page; HTMX sends CSRF automatically if the token is in the page's cookies (Django default) or via headers (custom integration).

Where to find handlers
- `accounting/views/views_journal_grid.py` — contains `journal_entry_add_row`, `journal_entry_grid_add_row`, `account_lookup`, etc.
- `accounting/views/journal_entry.py` — larger collection of journal entry views and HTMX utilities used across the app.

