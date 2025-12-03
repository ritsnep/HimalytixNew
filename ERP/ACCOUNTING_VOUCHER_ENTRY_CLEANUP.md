# Journal-Entry Consolidation Plan & Reference Map

This document outlines the plan to consolidate all voucher/journal entry functionality under the `journal-entry` UI, making `http://127.0.0.1:8000/accounting/journal-entry/` the canonical endpoint. All `voucher-entry` related components will be removed, archived, or migrated to support the `journal-entry` flow.

## Canonical Endpoint

The canonical endpoint for all journal/voucher entry functionality is:
- `http://127.0.0.1:8000/accounting/journal-entry/` (name=`accounting:journal_entry`)

## Duplicated Endpoints / Views / Templates (Candidates for Archival/Removal)

The following files and components are identified as `voucher-entry` related and should be archived or removed. Features from these components should be migrated to the `journal-entry` UI as needed.

### Templates
- `ERP/accounting/templates/accounting/voucher_entry.html`
- `ERP/accounting/templates/accounting/voucher_entry_new.html`
- `ERP/accounting/templates/accounting/voucher_entry_backup.html`
- `ERP/accounting/templates/accounting/partials/voucher_line_row.html` (if specific to voucher-entry)

### Views
- `ERP/accounting/views/views.py::VoucherEntryView` (This is a duplicate of the one in `voucher.py`. The one in `voucher.py` seems more feature-rich with schema resolution and custom validation rules. We need to decide which one to keep and rename it to `JournalEntryView` or similar, or consolidate their functionalities.)
- `ERP/accounting/views/voucher.py::VoucherEntryView` (See above. This is likely the one to keep and adapt for `journal-entry`.)
- `ERP/accounting/views/voucher_create_view.py::VoucherCreateView`
- `ERP/accounting/views/voucher_create_view.py::VoucherCreateHtmxView`
- `ERP/accounting/views/voucher_create_view.py::VoucherAccountLookupHtmxView`
- `ERP/accounting/views/voucher_create_view.py::VoucherTaxCalculationHtmxView`
- `ERP/accounting/views/voucher_edit_view.py::VoucherEditView`
- `ERP/accounting/views/voucher_detail_view.py::VoucherDetailView`
- `ERP/accounting/views/voucher_list_view.py::VoucherListView`
- `ERP/accounting/views/voucher_crud_views.py::VoucherListView`
- `ERP/accounting/views/voucher_crud_views.py::VoucherCreateView`
- `ERP/accounting/views/voucher_crud_views.py::VoucherDetailView`
- `ERP/accounting/views/voucher_crud_views.py::VoucherUpdateView`
- `ERP/accounting/views/voucher_crud_views.py::VoucherDeleteView`
- `ERP/accounting/views/voucher_crud_views.py::VoucherDuplicateView`
- `ERP/accounting/views/voucher_crud_views.py::VoucherPostView`
- `ERP/accounting/views/voucher_htmx_handlers.py` (entire file, if all handlers are voucher-specific)
- `ERP/accounting/views/voucher_views.py` (entire file, if all views are legacy voucher-specific)

### URLs (from `ERP/accounting/urls.py`)
- `/accounting/voucher-entry/` (name=`accounting:voucher_entry_list`)
- `/accounting/voucher-entry/create/` (name=`accounting:voucher_entry_create`)
- `/accounting/voucher-entry/create/<str:journal_type>/` (name=`accounting:voucher_entry_create_typed`)
- `/accounting/voucher-entry/<int:pk>/` (name=`accounting:voucher_entry_detail`)
- `/accounting/voucher-entry/<int:pk>/edit/` (name=`accounting:voucher_entry_edit`)
- `/accounting/voucher-entry/htmx/add-line/` (name=`accounting:voucher_entry_add_line_hx`)
- `/accounting/voucher-entry/htmx/account-lookup/` (name=`accounting:voucher_entry_account_lookup_hx`)
- `/accounting/voucher-entry/htmx/tax-calculation/` (name=`accounting:voucher_entry_tax_calculation_hx`)
- `/accounting/voucher-entry/` (name=`accounting:voucher_entry`) - *This is a duplicate entry in urls.py, needs to be removed.*
- `/accounting/voucher-entry/<int:config_id>/` (name=`accounting:voucher_entry_config`) - *This is a duplicate entry in urls.py, needs to be removed.*
- All URLs under `path('vouchers/', ...)` and `path('vouchers/htmx/', ...)` related to `voucher_crud_views` and `voucher_htmx_handlers`.

### Models/Migrations
- `ERP/accounting/models.py` (references to `scope="voucher_entry"` in `VoucherUIPreference` and permissions like `add_voucher_entry`)
- `ERP/accounting/migrations/0025_alter_journal_options_alter_fiscalyear_id.py` (permissions related to `voucher_entry`)
- `ERP/accounting/migrations/0048_alter_journal_options_and_more.py` (permissions related to `voucher_entry`)
- `ERP/accounting/migrations/0146_alter_fiscalyear_id_voucheruipreference.py` (references to `scope='voucher_entry'`)

### Static Assets
- `ERP/accounting/templates/accounting/journal_entry.html` (references `voucher_entry.css` and `voucher_entry.js`)
- `ERP/accounting/css/voucher_entry.css`
- `ERP/accounting/css/voucher_entry_dason.css`
- `ERP/accounting/js/voucher_entry.js`

## References to Update

All references to `voucher_entry` in templates, views, and tests should be updated to point to the canonical `journal_entry` endpoints or removed if the functionality is no longer needed.

- `ERP/accounting/views/voucher_detail_view.py` (redirects to `voucher_entry_edit`, `voucher_entry_detail`)
- `ERP/accounting/views/voucher_edit_view.py` (redirects to `voucher_entry_detail`)
- `ERP/accounting/views/voucher_crud_views.py` (references `voucher_entry_new`, `voucher_entry_page`, `cancel_url` to `voucher_detail`)
- `ERP/accounting/views/voucher_create_view.py` (redirects to `voucher_entry_detail`)
- `ERP/accounting/views/journal_entry.py` (references `voucher_entry_page`, `scope="voucher_entry"`)
- `ERP/accounting/tests/test_views.py` (tests for `voucher_entry`, `voucher_entry_config`)
- `ERP/accounting/tests/test_voucher_view.py` (tests for `voucher_entry_config`)
- `ERP/accounting/templates/accounting/base_voucher.html` (links to `voucher_entry_list`, `voucher_entry_add_line_hx`)
- `ERP/accounting/templates/accounting/base.html` (links to `voucher_entry_list`, `voucher_entry_create`)
- `ERP/accounting/templates/accounting/journal_entry_detail.html` (links to `voucher_entry_list`, `voucher_entry_edit`)
- `ERP/accounting/templates/accounting/journal_entry_list.html` (links to `voucher_entry_create`, `voucher_entry_detail`)
- `ERP/accounting/templates/accounting/voucher_entry.html` (contains `voucher-entry-container`, `voucher-entry-form`)
- `ERP/accounting/templates/accounting/vouchers/voucher_header.html` (redirects to `/accounting/voucher-entry/` + configId)

## Migration of Features

The following features from `voucher-entry` components should be carefully reviewed and migrated to the canonical `journal-entry` UI and its supporting views (e.g., `ERP/accounting/views/views.py::JournalEntryView` or a new dedicated `JournalEntryView`):

### From `ERP/accounting/views/voucher.py::VoucherEntryView`
- **Schema Resolution and Dynamic Form Building:** The `_get_voucher_schema` and `_create_voucher_forms` methods in `ERP/accounting/views/voucher.py` provide robust schema-driven form generation, including:
    - Dynamic inclusion/exclusion of dimensional fields (department, project, cost_center) based on `VoucherModeConfig`.
    - Dynamic inclusion/exclusion of tax details.
    - Enforcement of required line descriptions.
    - Handling of multi-currency fields.
    - Injection of User-Defined Fields (UDFs) into header and line schemas.
- **Custom Validation Rules:** Implementation of custom validation rules defined in `VoucherModeConfig` (e.g., `max_lines`, `debit_accounts_only`, `no_tax_without_account`).
- **Single-Entry Auto-Balancing:** The logic for automatically balancing single-entry vouchers using a default ledger account.

### From `ERP/accounting/templates/accounting/voucher_entry.html` and `voucher_entry_new.html`
- **Dynamic UI Rendering:** The ability to dynamically render form fields and sections based on the `VoucherModeConfig` and its associated schema.
- **HTMX-driven Interactions:** Any advanced HTMX interactions for adding/removing lines, account lookups, tax calculations, and real-time validation should be integrated.
- **Client-side Validation:** JavaScript-based validation for debit/credit balance and other immediate feedback.
- **Voucher Configuration Selection:** The mechanism for users to select different voucher configurations to change the form's behavior and appearance.

### From `ERP/accounting/views/voucher_crud_views.py` and `voucher_htmx_handlers.py`
- **CRUD Operations:** Ensure that the `journal-entry` flow supports comprehensive Create, Read, Update, and Delete (CRUD) operations for journal entries and their lines, potentially incorporating robust error handling and messaging.
- **HTMX Handlers:** Migrate essential HTMX handlers for dynamic line management, account lookups, tax calculations, and status validations to support the `journal-entry` UI.

## Suggested Git Move Commands (Example)

Create a branch and an archive folder, then `git mv` the legacy files into it. Example (PowerShell):

```powershell
git checkout -b cleanup/consolidate-journal-entry
mkdir -Force ERP\accounting\archive\voucher_entry
git mv ERP\accounting\templates\accounting\voucher_entry.html ERP\accounting\archive\voucher_entry\voucher_entry.html
git mv ERP\accounting\templates\accounting\voucher_entry_new.html ERP\accounting\archive\voucher_entry\voucher_entry_new.html
git mv ERP\accounting\templates\accounting\voucher_entry_backup.html ERP\accounting\archive\voucher_entry\voucher_entry_backup.html
git mv ERP\accounting\templates\accounting\partials\voucher_line_row.html ERP\accounting\archive\voucher_entry\partials\voucher_line_row.html
git mv ERP\accounting\views\voucher.py ERP\accounting\archive\voucher_entry\voucher.py
git mv ERP\accounting\views\voucher_create_view.py ERP\accounting\archive\voucher_entry\voucher_create_view.py
git mv ERP\accounting\views\voucher_edit_view.py ERP\accounting\archive\voucher_entry\voucher_edit_view.py
git mv ERP\accounting\views\voucher_detail_view.py ERP\accounting\archive\voucher_entry\voucher_detail_view.py
git mv ERP\accounting\views\voucher_list_view.py ERP\accounting\archive\voucher_entry\voucher_list_view.py
git mv ERP\accounting\views\voucher_crud_views.py ERP\accounting\archive\voucher_entry\voucher_crud_views.py
git mv ERP\accounting\views\voucher_htmx_handlers.py ERP\accounting\archive\voucher_entry\voucher_htmx_handlers.py
git mv ERP\accounting\views\voucher_views.py ERP\accounting\archive\voucher_entry\voucher_views.py
git mv ERP\accounting\css\voucher_entry.css ERP\accounting\archive\voucher_entry\voucher_entry.css
git mv ERP\accounting\css\voucher_entry_dason.css ERP\accounting\archive\voucher_entry\voucher_entry_dason.css
git mv ERP\accounting\js\voucher_entry.js ERP\accounting\archive\voucher_entry\voucher_entry.js
git add -A
git commit -m "chore: archive legacy voucher-entry templates, views, and static assets"
```

## Quick Checklist for Updates

- **URLs:** Remove all `voucher-entry` related paths from `ERP/accounting/urls.py`.
- **Templates:** Update all `{% url 'accounting:voucher_entry_...' %}` occurrences to `{% url 'accounting:journal_entry_...' %}` or `{% url 'accounting:journal_...' %}` where appropriate.
- **Views:**
    - Consolidate `VoucherEntryView` implementations. The one in `ERP/accounting/views/voucher.py` appears more feature-rich and should be considered for integration into `ERP/accounting/views/views.py::JournalEntryView` or a new dedicated `JournalEntryView`.
    - Update any redirects or `reverse()` calls in views that currently point to `voucher-entry` URLs.
    - Migrate any unique logic from `voucher-entry` views to `journal-entry` views.
- **Tests:** Update tests that `reverse('accounting:voucher_entry')` or similar to use `journal-entry` routes or to target API endpoints used by `journal-entry` flows.
- **Models/Migrations:** Review and update `VoucherUIPreference` scope and permissions related to `voucher_entry` to `journal_entry`.
- **Static Assets:** Remove `voucher_entry.css`, `voucher_entry_dason.css`, and `voucher_entry.js` after ensuring their functionalities are either no longer needed or have been migrated to `journal-entry` specific assets.
