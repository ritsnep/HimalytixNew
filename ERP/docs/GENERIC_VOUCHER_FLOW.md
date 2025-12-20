# Generic Voucher Entry Flow (Single Source of Truth)

This document defines the production contract for the Generic Voucher Entry System, including invariants, runtime behavior, and HTMX UX guarantees.

## 0) Scope and Guarantees (Non‑Negotiable)
Supported subsystems: Accounting, Purchasing, Sales/Billing, Bank/Cash, Inventory.

System invariants:
- Voucher and Journal are 1:1 for accounting vouchers unless explicitly configured as 1:N (document the exception per voucher type).
- Journal is always balanced: Σdebit = Σcredit (within rounding tolerance).
- Posting is idempotent: multiple posts produce a single posted result.
- Posting is atomic: either all effects occur or none occur (or deterministic saga compensations if distributed).
- Posted vouchers are immutable; changes require reversal + repost (no in-place edits).
- Every posting emits an audit trail (who/when/what/service step).

## 1) Architecture Overview
Single source of truth:
- Voucher definition lives in `VoucherModeConfig.schema_definition` (normalized schema).
- UI schema is derived via `VoucherModeConfig.resolve_ui_schema()`.
- Legacy `ui_schema` JSON is not used at runtime.

Separation of concerns:
- Voucher Definition (config): schema, workflow, mappings, policy.
- Voucher Instance (runtime): header/lines, status, idempotency key, version.
- Posting Execution (operational): step logs, timings, failures, retriable state.
- Audit/History: immutable journal and snapshot history.

## 2) Voucher Definition Model (Config)
Schema format:
- Controlled vocabulary for `field_type` (text/textarea/date/decimal/integer/boolean/select/lookup/typeahead/etc).
- `header_fields[]` and `line_fields[]` with `key`, `label`, `field_type`, `required`, `validators`, `ui`.
- Explicit ordering via `__order__` derived from the definition.

Workflow definition:
- Draft → Pending Approval → Posted (plus Approved/Rejected/Failed if enabled).
- Allowed transitions are enforced server-side.

Journal mapping:
- Each voucher maps to a JournalType by stable code.
- Mappings must be deterministic and seeded per organization.

Customization hooks:
- UDFs (user-defined fields) without DB migration.
- Field visibility by org/branch/role.
- Conditional required rules and dynamic defaults.

## 3) Runtime Data Model
Voucher Instance:
- Journal header + JournalLines.
- Voucher status, idempotency key, rowversion for concurrency.

Inventory metadata (required for inventory vouchers):
- voucher_id, voucher_line_id
- journal_id, journal_line_id
- org_id, fiscal_year_id
- transaction_date, warehouse_id, product_id, uom_id
- quantity, unit_cost, valuation_method snapshot
- batch/serial/location (when applicable)
- grir_account_id (receipt), cogs_account_id (issue)

Posting execution log (recommended):
- attempt_id, voucher_id, started_at, ended_at, actor
- step_name, step_status, error_code, error_payload
- correlation_id for tracing

## 4) Form Generation Contract
Single entry point:
- `VoucherFormFactory` generates header + line formset.

Validation injection:
- required, regex, min/max, precision, step, disabled/readonly.
- any invalid field blocks save/post.

Ordering:
- __order__ respected for header/lines.
- column layout supports large field counts via horizontal scroll.

## 5) HTMX UI Contract (No Refresh)
Component boundaries:
- header, lines table, totals panel, stepper, error banner.

Endpoint responsibilities:
- validate/recalc/save/post/status (partial responses).

Response rules:
- 200 + partial for success
- 422 + partial for validation errors
- 409 + partial for concurrency conflict
- 403 + partial for permissions
- never return a full HTML error page to an interactive voucher action

HTMX events:
- `voucher:saved`, `voucher:recalc`, `voucher:post_started`, `voucher:post_failed`, `voucher:posted`

Double-submit protection:
- disable buttons client-side
- idempotency key server-side

## 6) Posting Orchestration Contract
Steps:
1. Validate header + lines
2. Save voucher (draft)
3. Create Journal + JournalLines
4. Post GL
5. Post Inventory (if applicable)
6. Mark posted

Atomic behavior:
- single DB: `transaction.atomic()`
- distributed: saga with compensations (void journal, reverse GL, rollback inventory)

Idempotency:
- posting on an already posted voucher returns safely without duplicates.

## 7) Inventory + GL Posting Rules
- Valuation: FIFO/Weighted Avg (per product config).
- GR/IR handling for receipts.
- COGS for issues.
- Rounding differences handled explicitly.

## 8) Security and Permissions
- Direct-post permission bypasses approval (if allowed).
- Approval matrix can be multi-level (amount/branch/cost center).
- Period locks and audit locks are enforced on posting.

## 9) Seeding and Org-wise Defaults
- Master templates → org instantiation.
- Idempotent seed commands.
- JournalType seeds must exist before voucher config seeding.

## 10) Testing and Monitoring
Required tests:
- rollback on inventory failure
- idempotent posting
- mapping correctness (voucher → journal type)
- concurrency (double-post, rowversion conflict)

Observability:
- correlation IDs across services
- voucher process logs with step timing and error codes

## Current Implementation Notes
UI flow (HTMX):
1. User opens voucher type selection: `VoucherTypeSelectionView`.
2. UI loads the form using `GenericVoucherCreateView`.
3. Lines added via HTMX: `GenericVoucherLineView`.
4. Totals/footer recalculated via `POST /accounting/generic-voucher/recalc/`.
5. Stepper updated via HX-Trigger payloads.

Error propagation:
- `VoucherProcessError` carries stable codes: INV-*, GL-*, VCH-*.

## Key Files
- Config model: `ERP/accounting/models.py` (VoucherModeConfig)
- Schema conversion: `ERP/accounting/voucher_schema.py`
- Form factory: `ERP/accounting/forms_factory.py`
- Orchestration: `ERP/accounting/services/create_voucher.py`
- Posting: `ERP/accounting/services/posting_service.py`
- Seeding: `ERP/accounting/services/voucher_seeding.py`
- Generic voucher views: `ERP/accounting/views/generic_voucher_views.py`
- HTMX panel: `ERP/accounting/templates/accounting/partials/generic_voucher_form_panel.html`
- Summary partial: `ERP/accounting/templates/accounting/partials/generic_voucher_summary.html`
