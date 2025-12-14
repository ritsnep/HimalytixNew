# Voucher Entry System — README

## Overview

This document describes the Voucher Entry subsystem implemented in the `accounting` app: goals, developer setup, tests and verification steps, proposed data model & API improvements, UI flow and behavior, known edge-cases and risks, and a recommended PR plan to complete remaining work and harden the feature.

This README is intended for developers and reviewers who will extend or stabilize the Voucher Entry system (Phase 1+2 work). It assumes familiarity with Django, HTMX, and the project's Dason/Bootstrap front-end conventions.

---

## Goals

- Implement an HTMX-driven voucher entry UI with parity to Journal Entry UX.
- Keep server-side rendering for rows & row fragments (HTMX partials) while enabling progressive enhancement and JS-based convenience features.
- Support voucher configuration (`VoucherModeConfig`) and user-defined fields (`VoucherUDFConfig`) with API endpoints and seed scripts.
- Add robust tests and reproducible developer verification steps.

---

## Quick Start — Dev & Test

1. Setup (existing project):

   - Create & activate your virtual env, install dependencies from `ERP/requirements.txt`.
   - Create a dev DB and apply migrations:

       .\venv\Scripts\python.exe manage.py migrate
       .\venv\Scripts\python.exe manage.py createsuperuser  # if needed
       .\venv\Scripts\python.exe scripts/seed_database.py    # ensure `STANDARD` voucher config

2. Run the dev server and open the Voucher Entry page:

       .\venv\Scripts\python.exe manage.py runserver
   then visit http://127.0.0.1:8000/accounting/vouchers/new/ (or /accounting/voucher-entry/ as appropriate)

3. Notes for Django test client tests and HTMX endpoints: pass `HTTP_HOST='127.0.0.1'` or set `ALLOWED_HOSTS` in test settings to avoid `DisallowedHost` during POST/HTMX tests.

---

## Files & Components to inspect

- Templates
  - `accounting/templates/accounting/voucher_entry_new.html` — main page & `#app` bootstrap area
  - `accounting/templates/accounting/htmx/voucher_entry_grid.html` — grid partial
  - `accounting/templates/accounting/htmx/voucher_entry_grid_row.html` — row partial

- Views / Handlers
  - `accounting/views/views_journal_grid.py` — existing HTMX handlers reused
  - `accounting/views/journal_entry.py` — journal helper functions
  - `accounting/views/voucher_crud_views.py` and `accounting/views/voucher_htmx_handlers.py`

- JS
  - `accounting/static/js/voucher_htmx.js` — HTMX bindings & debug helpers
  - `accounting/static/accounting/voucher_entry/app.js` — SPA-like manager used for client-side features

- Models
  - `accounting.models.VoucherModeConfig`
  - `accounting.models.VoucherUDFConfig`

---

## Checklist — What to test (developer / reviewer)

Unit & Integration tests (automated):

- [ ] HTMX add-row: POST to add-row endpoint returns 200 and a valid row HTML fragment.
- [ ] Inline edit: POST row update endpoint persists change and returns refreshed row or status 200.
- [ ] Duplicate/delete row endpoints: return expected status and modify line sets.
- [ ] UDF API CRUD: create (201), read (200), patch (200), delete (204) for `/forms_designer/api/udfs/`.
- [ ] Account lookup endpoint returns suggestions for partial names/codes (test with seeded ChartOfAccount).
- [ ] Ensure `VoucherModeConfig` seeding script sets `STANDARD` and `is_default=True`.

Manual tests / QA steps:

- [ ] Load `/accounting/vouchers/new/` as admin — page loads, `#app` exists and initial state is present.
- [ ] When the grid is empty, the UI auto-adds a first line (Add Line triggered).
- [ ] Toggle debug mode (via `journal_debug_enabled`) to confirm debug console logs and visual flashes appear only in debug.
- [ ] Large Chart-of-Accounts: test select/typeahead performance (see proposed change below).

Test notes:

- When using Django `Client()` in tests, use `c.get(url, HTTP_HOST='127.0.0.1')` to avoid DisallowedHost. CI may need `ALLOWED_HOSTS` set.

---

## Proposed Data Model Changes (suggested for stability and features)

These are optional but recommended to support scale & features such as typeahead suggestions, row audit, and UDF indexing.

1. VoucherLine (if not already explicitly modeled)

   - Add a `VoucherLine` model (if current implementation stores lines as formsets only) with columns:
     - `id`, `voucher` (FK), `position` (int), `account` (FK to ChartOfAccount, indexed), `description` (text), `debit` (Decimal), `credit` (Decimal), `cost_center` (FK optional), `udf_data` (JSONField optional), `created_by`, `created_at`, `modified_at`.
   - Rationale: Having a persisted `VoucherLine` object simplifies back-end validation endpoints, auditing, and row-level HTMX operations.

2. Voucher (header)

   - Ensure `Voucher` has `status` enum (Draft/Submitted/Posted/Rejected), `journal_type` FK, `org`/`tenant` link, `total_debit`, `total_credit`, `balanced` boolean.

3. UDF Indexes

   - For heavy UDF usage, consider a separate `VoucherUDFValue` model to index searchable UDFs (or at least index JSONField keys used for queries).

4. Audit / Soft-delete

   - Add `is_deleted` boolean or soft-delete mixin for lines and vouchers for safe recovery and audit trails.

Backward compatibility: Add data migrations where possible; keep API backward-compatible during rollouts.

---

## Proposed API Endpoints (existing + suggested)

Existing endpoints to keep / verify

- GET `/accounting/vouchers/new/` (page)
- HTMX (journal reuse):
  - POST `/journal-entry/add-row/` — returns row fragment
  - POST `/journal-entry/row/` — update inline
  - POST `/journal-entry/duplicate-row/` — duplicate row
  - DELETE `/journal-entry/row/` — delete row
- Voucher HTMX handlers:
  - POST `/vouchers/<journal_id>/htmx/add-line/`
  - GET `/vouchers/htmx/account-lookup/` (typeahead)

Suggested new/revised endpoints (to add for clarity and testability):

1. REST-style lines API (wrap HTMX ops with REST endpoints):

   - POST `/api/v1/vouchers/{voucher_id}/lines/` — create a line (returns JSON or row HTML based on Accept header)
   - PATCH `/api/v1/vouchers/{voucher_id}/lines/{line_id}/` — update line
   - DELETE `/api/v1/vouchers/{voucher_id}/lines/{line_id}/` — delete line

2. Account typeahead (improved):

   - GET `/api/v1/accounts/suggest/?q=...&limit=10` — returns JSON list of `{id, code, name, display}` for fast typeahead.

3. Voucher validation and balancing endpoints:

   - POST `/api/v1/vouchers/{voucher_id}/validate/` — run server-side validation rules and return list of errors/warnings.
   - POST `/api/v1/vouchers/{voucher_id}/auto-balance/` — attempt server-side balancing (distribute imbalance or return an actionable error).

4. UDF management (already exists) — ensure `/forms_designer/api/udfs/` is stable & documented.

Notes: Keep HTMX endpoints for immediate UI partials but provide API alternatives to ease testing and automation.

---

## UI Flow & Behaviour

Flow summary:

1. Load `/vouchers/new/` (or typed by config): server provides `initial_state` JSON and `#app` area.
2. On empty grid, client auto-triggers Add Line (user sees first row ready for input).
3. Account field supports lookup/typeahead — sends queries to account lookup endpoint; selecting a suggestion fills the account and updates row.

Note: A lightweight typeahead was added (JS + datalist) that queries `/accounting/vouchers/htmx/account-lookup/` and updates the hidden account input which triggers existing HTMX row updates.
4. Debit/credit inputs post updates to the row HTMX endpoint (on blur) and server returns a refreshed row fragment.
5. Add Row button posts to add-line HTMX endpoint and appends a row fragment.
6. Duplicate/Delete actions post to respective HTMX endpoints and the UI updates the fragile portions (totals, rows) on swap.
7. Save/Submit actions call server endpoints to persist voucher header and lines, run validation, and route to Post/Approval flows.

UX notes:

- Keep the sticky action bar visible; keep debug console hidden in production.
- Keyboard-first workflows are desirable: support Enter to confirm, Tab to move across inputs, Arrow keys to navigate. (Pending work)

---

## Edge Cases and Validation Rules

Edge cases to handle and test:

- Imbalanced entries: warn on save; optionally prevent Submit until balanced depending on config.
- Rounding differences: floating point rounding must be deterministic (use Decimal arithmetic server-side).
- Empty account/invalid account: row updates must validate account FK and return an inline error.
- Concurrent edits: two users editing the same voucher — design optimistic concurrency (version or last-modified check) or lock on edit.
- Large Chart of Accounts: ensure typeahead only returns small result sets and applies a server-side limit.
- UDFs with required fields: when header-level UDFs are required, block save/submit if missing.
- Invalid HTMX swaps: server must return appropriate status & helpful fragment when validation fails (e.g., return 400 + error html fragment with `hx-swap-oob` to place error messages).

---

## Risks & Mitigations

- DisallowedHost errors in tests: mitigate by setting `HTTP_HOST='127.0.0.1'` in tests or set `ALLOWED_HOSTS` accordingly.
- UX regressions when replacing selects with typeahead: roll out behind feature flag and add UI tests.
- Data model migrations: add data migration scripts and run in a staging environment.
- HTMX fragility (swaps failing leaving inconsistent UI): ensure robust server-side validation and design idempotent endpoints.
- Performance with huge COA: implement server-side pagination, search by prefix, and caching for top-level accounts.

---

## PR Plan (3–5 PRs)

Below is a recommended sequence of PRs to break work into reviewable changes. Each PR should include tests and documentation updates as applicable.

PR 1 — Foundation & Docs (small, safe)

- Add `accounting/docs/voucher_entry_README.md` (this doc) and the architecture & test results files.
- Add tests that assert current HTMX add-row and UDF API basic behavior.
- No DB schema changes.

PR 2 — Account Typeahead & API

- Add a JSON `account-suggest` endpoint `/api/v1/accounts/suggest/`.
- Replace account `<select>` (or augment) with HTMX/JS typeahead that uses the new API.
- Add tests for account lookup and client integration (js-wtr or integration tests).

PR 3 — RESTful Line APIs + Persistence

- Add `VoucherLine` model and REST endpoints (`/api/v1/vouchers/{id}/lines/`), add migrations.
- Migrate existing HTMX handlers to use the new model where appropriate.
- Add unit tests & integration tests verifying create/update/delete and that HTMX endpoints can return row fragments or JSON.

PR 4 — UX Improvements & Keyboard Support

- Add keyboard navigation and fast entry behavior (Tab/Enter/Arrow keys), ensure accessibility.
- Add integration tests that drive keyboard flows and HTMX swaps.

PR 5 — Hardening, Performance & Conformance

- Add audit trail support (created_by, timestamps), soft-delete, and data migrations.
- Add pagination/caching for account suggestions for large datasets.
- Add comprehensive end-to-end tests (pytest + wtr for JS flows) and CI job updates if needed.

Notes on PR strategy:

- Keep PRs small and focused; each PR should have passing unit tests and at least one integration test for the main feature.
- Use feature flags for UX changes that might be disruptive.

---

## Example test snippets

Use Django test client with host header:

    from django.test import Client
    from django.contrib.auth import get_user_model

    User = get_user_model()
    admin = User.objects.filter(is_superuser=True).first()
    client = Client()
    client.force_login(admin)
    resp = client.post('/accounting/journal-entry/add-row/', HTTP_HOST='127.0.0.1')
    assert resp.status_code == 200
    assert 'id="line-' in resp.content.decode()

---

If you'd like, I can now implement PR 2 (account typeahead & API) or PR 3 (VoucherLine model + REST lines API). Which do you want me to start with? I can also open the initial PR draft and tests for PR 1 immediately.
