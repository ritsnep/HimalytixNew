# Voucher-Entry Cleanup Plan & Reference Map

This file lists duplicated voucher/journal entry endpoints, templates, views, and all tests/templates/docs that reference the legacy HTMX `journal_entry` UI. Use this when archiving legacy files and updating references so the project has one canonical `voucher-entry` UI.

## Duplicated endpoints / views / templates (candidates to archive)

- `ERP/accounting/templates/accounting/journal_entry.html`  — HTMX spreadsheet-like journal UI (archive)
- `ERP/accounting/templates/accounting/_journal_line_row.html` — HTMX row fragment (archive)
- `ERP/accounting/templates/accounting/partials/line_empty_form.html` — HTMX empty row fragment (archive)
- `journal_entry_replace_pack/` (entire directory) — drop-in replacement bundle with duplicate `journal_entry.html` and static assets (archive)
- `ERP/accounting/templates/accounting/voucher_entry_backup.html` — preserved backup (move to archive)
- Duplicate `VoucherEntryView` classes:
  - `ERP/accounting/views/views.py::VoucherEntryView`
  - `ERP/accounting/views/voucher.py::VoucherEntryView`
  (review and keep the canonical implementation; archive the duplicate)
- Static duplicates inside the replace-pack:
  - `journal_entry_replace_pack/.../static/accounting/js/voucher_entry.js`
  - `journal_entry_replace_pack/.../static/accounting/css/voucher_entry.css`

## Journal/HTMX endpoints (legacy) referenced in `ERP/accounting/urls.py`

These routes are part of the HTMX journal flow and are candidates for removal / consolidation if you want only the `voucher-entry` UI:

- `/accounting/journal-entry/` (name=`accounting:journal_entry`) and supporting endpoints:
  - `/accounting/journal-entry/save-draft/` (`journal_save_draft`)
  - `/accounting/journal-entry/submit/` (`journal_submit`)
  - `/accounting/journal-entry/approve/` (`journal_approve`)
  - `/accounting/journal-entry/reject/` (`journal_reject`)
  - `/accounting/journal-entry/post/` (`journal_post`)
  - `/accounting/journal-entry/htmx/get_row_template/` (row template)
  - `/accounting/journal-entry/lookup/accounts/` and similar lookups
  - attachment, prefs, payment-terms endpoints used by the HTMX UI

If you consolidate to `voucher-entry` these endpoints should be either removed or re-pointed to voucher-specific handlers.

## Tests, templates, and code references to update after archival

Search results for `accounting:journal_entry` show the following files referencing the legacy route — each should be updated to point to `accounting:voucher_entry` or adjusted as appropriate:

- `journal_entry_replace_pack/journal_entry_replace_pack/sidebar_snippet.html`
- `journal_entry_replace_pack/journal_entry_replace_pack/README-INSTALL.md`
- `ERP/tests/test_journal_entry_api.py` (references `accounting:journal_entry_data`) — update tests to use voucher endpoints or mock appropriately
- `ERP/templates/partials/left-sidebar.html` (sidebar link)
- `ERP/billing/templates/billing/invoice_create_template.html` (button/link to journal_entry)
- `ERP/accounting/views/journal_entry_view.py` (internal redirects; may reference `journal_entry_new`)
- `ERP/accounting/views/journal_entry.py` (uses `reverse('accounting:journal_entry_data')`)
- `ERP/accounting/services/report_service.py` (calls `reverse('accounting:journal_entry_detail', args=[journal_id])`)
- `ERP/accounting/tests/test_journal_entry_ui.py` (reverse('accounting:journal_entry'))
- `ERP/accounting/templates/accounting/journal_select_config.html` (JS `URL('{% url 'accounting:journal_entry' %}')`)
- `ERP/accounting/templates/accounting/partials/journal_grid_footer.html` (HX actions interacting with journal grid)
- `ERP/accounting/templates/accounting/voucher_list.html` (links: `href="{% url 'accounting:journal_entry' %}?voucher_id={{ voucher.pk }}`)
- `ERP/accounting/templates/accounting/journal_entry_grid.html` (data-add-row-url etc.)
- `ERP/accounting/management/commands/test_ui_interactions.py` (placeholder reverse calls to `accounting:journal_entry`)

Also update documentation references and flow docs that mention the HTMX UI and fragments:

- `ERP/accounting/JOURNAL_ENTRY_FLOW.md`
- `ERP/VOUCHER_ENTRY_FINALIZATION_REPORT.md` and other `ERP/VOUCHER_ENTRY_*` docs that show `journal_entry` examples
- `Docs/consolidated_todo_register.md` (mentions HTMX fragment templates)

## HTMX fragment includes to update or remove

If you archive the HTMX journal UI you'll need to remove or migrate these fragment templates and the views that render them:

- `ERP/accounting/templates/accounting/partials/line_empty_form.html` (rendered by `JournalEntryRowTemplateView`)
- `ERP/accounting/templates/accounting/_journal_line_row.html` (rendered by various journal views)
- Views producing fragments:
  - `ERP/accounting/views/journal_entry_view.py::JournalEntryRowTemplateView`
  - `ERP/accounting/views/journal_views.py` (renders `_journal_line_row.html`)
  - `ERP/accounting/views/journal_entry_view.py::JournalValidateLineView` (line validation)

## Suggested git move commands (example)

Create a branch and archive folder, then `git mv` the legacy files into it. Example (PowerShell):

```powershell
git checkout -b cleanup/consolidate-voucher-entry
mkdir -Force ERP\accounting\archive
git mv ERP\accounting\templates\accounting\journal_entry.html ERP\accounting\archive\journal_entry.html
git mv ERP\accounting\templates\accounting\_journal_line_row.html ERP\accounting\archive\_journal_line_row.html
git mv ERP\accounting\templates\accounting\partials\line_empty_form.html ERP\accounting\archive\line_empty_form.html
git mv ERP\accounting\templates\accounting\voucher_entry_backup.html ERP\accounting\archive\voucher_entry_backup.html
git mv journal_entry_replace_pack ERP\accounting\archive\journal_entry_replace_pack
git add -A
git commit -m "chore: archive legacy journal-entry HTMX templates and duplicate static assets"
```

After moves, update references listed above, run tests, and manually smoke-test `/accounting/voucher-entry/`.

## Quick checklist to update references

- Replace `{% url 'accounting:journal_entry' %}` occurrences with `{% url 'accounting:voucher_entry' %}` where appropriate.
- Update tests that `reverse('accounting:journal_entry')` to use voucher routes or to target API endpoints used by voucher-entry flows.
- Remove or update sidebar/navigation snippets that point to journal_entry.
- Ensure voucher list/detail pages link to voucher-entry endpoints instead of journal-entry.

---

If you want, I can now:

- Produce an automated `git mv` script with the exact files I found in this repo and open a branch with those moves (I will not commit without your approval). 
- Run a repo-wide replacement preview for `accounting:journal_entry` → `accounting:voucher_entry` and list proposed changes.

Tell me which action to take next.
