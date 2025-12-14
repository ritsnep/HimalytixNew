# Voucher Entry — Test Results Summary

This file captures the results from manual tests and quick API validations executed during the Phase 1 HTMX migration work.

Seed & Configuration

- `scripts/seed_database.py` executed to ensure required seed data exists.
  - `VoucherModeConfig` with `code='STANDARD'` exists and has `is_default=True`.

HTMX row operations

- Add-row (POST `/accounting/journal-entry/add-row/`) — success
  - Note: when using Django's test client, include `HTTP_HOST='127.0.0.1'` to avoid `DisallowedHost`.
  - Response: HTTP 200 with an HTML fragment beginning with `<div class="row align-items-center" id="line-1"`.

- Inline edit (POST to `/accounting/journal-entry/row/` via `hx-post`) — success

- Duplicate row (POST `/accounting/journal-entry/duplicate/`) — success

- Delete row (DELETE `/accounting/journal-entry/row/`) — success

Voucher UDF (forms designer API)

- Create (POST `/forms_designer/api/udfs/`) — returned 201 (created)
- Read (GET `/forms_designer/api/udfs/{id}/`) — returned 200
- Update (PATCH `/forms_designer/api/udfs/{id}/`) — returned 200 (updated display_name)
- Delete (DELETE `/forms_designer/api/udfs/{id}/`) — returned 204

Page load & UX checks

- GET `/accounting/vouchers/new/` as admin — HTTP 200 and page contains `Journal Lines` and `Add Line`.
- Auto-add-first-line behavior — on initial page load with empty grid, the UI triggers Add Line so a blank row is present, matching Journal Entry behavior.

Manual notes

- The HTMX debug flash and console were added to make swaps visible during development and can be disabled in production by removing the debug flags.
% Voucher Entry — Seed & CRUD Test Results

Summary of actions and outcomes performed on branch `main` (local dev env).

1) Seeded default data
- Used `scripts.seed_database` helper functions to ensure superuser, tenant, organization, journal types and voucher config are present.
- Command sequence (executed in `manage.py shell`):

```python
from scripts.seed_database import get_or_create_superuser, seed_tenancy, seed_organization, seed_journal_types, seed_voucher_mode_config
su = get_or_create_superuser()
tenant = seed_tenancy(su)
org = seed_organization(su, tenant)
seed_journal_types(org, su)
from accounting.models import JournalType
gj = JournalType.objects.filter(organization=org, code='GJ').first()
seed_voucher_mode_config(org, su, gj)
```

- Result: VoucherModeConfig with `code='STANDARD'` and `is_default=True` created (or already present).

2) Verified VoucherModeConfig presence
- Command (shell):

```python
from accounting.models import VoucherModeConfig
VoucherModeConfig.objects.filter(is_default=True).values('config_id','code','name','journal_type__code')
# -> returns the default Standard Voucher for journal type 'GJ'
```

3) Dependent model (Voucher UDF) CRUD
- Performed ORM and API CRUD checks for `VoucherUDFConfig`:
  - ORM: created `test_udf`, updated display_name, deleted — all operations succeeded.
  - API: POST to `/forms_designer/api/udfs/` to create `api_udf` returned 201; GET/PATCH/DELETE were tested and returned 200/200/204 respectively.

4) UI verification
- Fetched `/accounting/vouchers/new/` as an authenticated admin user and confirmed the page: status 200, contains `Journal Lines` header and `Add Line` button.
- The page uses the project's base template (`partials/base.html`) and the content is within the same main container used by dashboard pages.

5) Notes and next steps
- If you'd like, I can: auto-insert a blank row on load; convert the account select into an HTMX typeahead connected to `account_lookup`; or add integration tests (Django tests) asserting add-row returns valid HTML fragment.

If you want the detailed shell commands / transcripts saved as artifacts, I can add them to this doc or include them as files in `accounting/docs/`.
