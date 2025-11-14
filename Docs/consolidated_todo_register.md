# Consolidated TODO Register

This file replaces the scattered `ERP/TODO*.md`, `ERP/docs/JOURNAL_ENTRY_TODO.md`, and `ERP/V2/TODO*.md` artifacts. Each former document referenced below is retired, and its scope summary plus current verification note now live here so the team can track what still needs follow-up before we consider the project done.

## 1. Accounting Module & Journal Entry (former `ERP/TODO.md`)

**Scope highlights**
- Front-end formset hygiene, HTMX add/remove/validate endpoints, live validation panel, totals recalculation, and accessibility improvements for the journal entry grid.
- Server-side endpoints such as `/accounting/journals/add-line/`, `/accounting/journal/validate/`, `/accounting/journals/create/`, as well as posting rules, closed-period guards, and locking.
- Testing/performance/CI coverage: unit/integration/e2e suites plus artificial data benchmarks, coverage gates, and GitHub Actions jobs.
- Bonus snippets/prompts for the agent (add/remove logic, totals, validation panel) and optional UX enhancements to chase after the MVP.

**Status**
- Verified (feature evidence): `ERP/accounting/views/journal_entry_view.py` now hosts `JournalEntryRowTemplateView`, `JournalValidateLineView`, and other helpers that serve the HTMX templates (`ERP/accounting/templates/accounting/partials/line_empty_form.html`) so new rows can be rendered with `lines-__prefix__` placeholders, hidden delete flags, and accessible legends. The row fragment (`ERP/accounting/templates/accounting/_journal_line_row.html`) wires hx-validate calls for debit/credit and account lookups plus dynamic status badges, fulfilling the add/remove/validation requirements.
- Client-side behavior (totals, status badges, action gating, attachment hooks) lives in `ERP/accounting/static/accounting/js/voucher_entry.js` (see totals engine around `computeTotals()` and the render logic at ~820–1100) and is wired alongside the `#app` data attributes in `ERP/accounting/templates/accounting/journal_entry.html`.
- Endpoint coverage is exercised by `ERP/accounting/tests/test_journal_entry_ui.py`, which confirms the namespace resolves `journal_save_draft`, `journal_submit`, `journal_post`, and the related lookups/validation URLs (lines 1–70 show URL resolution for a working namespace).
- Posting & workflow services referenced in the original doc (such as `ERP/accounting/services/posting_service.py`, `ERP/accounting/services/journal_entry_service.py`, and permission helpers in `ERP/accounting/views/journal_entry.py`) already exist, so the backend safety net underlying the UI layers remains intact.

**Next steps**
- Execute the regression suites mentioned in the plan (ERP/accounting/tests/*) that cover posting, depreciation, reconciliation, and workflow services, then document any remaining acceptance gaps before closing this section.

## 2. Tally-Inspired Enhancements (former `ERP/TODO2.md`)

**Scope highlights**
- Add voucher types (Contra, Debit Note, Credit Note) with enforcement rules and seeded defaults.
- Build budget tracking/UI, comparative P&L/Balance Sheet/Cash Flow reports, cheque and bank utilities, bank reconciliation automation, multi-currency/FX tables, interest schedules, and keyboard shortcuts.
- Provide manual QA checklists, load/performance targets, and a deployment checklist covering coverage thresholds, staging validation, migrations, CI/CD artifacts, logging/monitoring, and post-deployment sanity checks.

**Status**
- Partially verified: core services exist (`ERP/accounting/services/app_payment_service.py`, `ERP/accounting/services/budget_service.py`, `ERP/accounting/services/tax_liability_service.py`, `ERP/accounting/services/bank_reconciliation_service.py`, `ERP/accounting/services/workflow_service.py`, etc.), signalling that the foundation for payment scheduling, budgeting reports, tax exports, and workflow audits is in place. Each service also has a corresponding test file (`ERP/accounting/tests/test_app_payment_service.py`, `test_budget_service.py`, `test_tax_liability_service.py`, `test_bank_reconciliation_service.py`, `test_workflow_service.py`) that exercises the core logic.
- Higher-level checklist items (cheque printing, interest calc, parallel ledgers, deployment readiness) still require explicit QA confirmation even though the underlying building blocks exist; keep this section active until the manual QA checklist and performance targets from the original plan are signed off.

**Next steps**
- Coordinate with QA to verify those multi-currency, reporting, and deployment checklist items, then document what is complete so we can remove this section or mark it done.

## 3. Journal Entry Replacement Pack (former `ERP/docs/JOURNAL_ENTRY_TODO.md`)

**Scope & status**
- The document lists rollout items for the journal-entry replacement pack and concludes with "Follow-up enhancements can iterate on dedicated attachment UX and richer auto-complete widgets, but the original TODO list is complete."
- Status: **Completed per the original file**. There were no remaining actions beyond standard verification.

## 4. Streamlit V2 TODO Series (paused per request)

### 4.1 Master checklist (`ERP/V2/TODO.md`)

**Scope**
- Milestones M0-M6 covering the Streamlit V2 UI at `/V2`: skeleton, auth bridge, analytics, voucher flows, observability, security/performance hardening, and CI/CD/deployment.
- High-level actions: Scaffold Streamlit `pages/`, wire the signed auth handshake, propagate tenancy headers, expose optimized DRF APIs, align security headers, deploy via Docker/NGINX, and surface metrics/traces/log fields.

**Status**
- Partial implementation exists (`ERP/V2/app.py` plus a `pages/` directory), but milestones beyond the skeleton still need verification.

**Next steps**
- Re-check M1-M6, verify token exchange flows, dashboards, voucher experiences, and observability endpoints for `/V2`, and document remaining acceptance gaps.

### 4.2 Auth Bridge (`ERP/V2/TODO_AUTH.md`)

**Scope**
- Timestamp-signed tokens, TTL/refresh, `/api/v1/auth/streamlit/issue/` and `/verify/`, `StreamlitTokenAuthentication`, permissions (`IsAuthenticated`, `HasActiveTenant`), rate limiting, and Streamlit helpers to store and refresh the token.

**Status**
- Not verified; confirm by reviewing the Django auth endpoints and the Streamlit API client wrappers under `ERP/V2/lib/`.

### 4.3 Tenancy Propagation (`ERP/V2/TODO_TENANCY.md`)

**Scope**
- Tenant header requirements, `HasActiveTenant` permission, middleware tweaks, unit tests for missing or mismatched tenants, a Streamlit tenant switcher, and logging fields.

**Status**
- Not verified; validate that every Streamlit request sends `X-Tenant-ID` and that the middleware/auth classes enforce the claim.

### 4.4 API Endpoints (`ERP/V2/TODO_API.md`)

**Scope**
- Versioned `/api/v1/v2/` routes for metrics, trial balance, ledger explorer, charts, vouchers, and voucher posting plus token issue/verify endpoints; focus on efficient queries, pagination, caching, and abuse protection.

**Status**
- Not verified; inspect DRF views/serializers for the promised endpoints and ensure indexes/limits/tests match the plan.

### 4.5 UI Pages (`ERP/V2/TODO_UI.md`)

**Scope**
- Streamlit pages (dashboard, trial balance, ledger explorer, voucher list/detail, settings), helper modules (`lib/api_client.py`, `lib/charts.py`, `lib/tables.py`, `lib/state.py`), UX polish (theme alignment, compact tables, empties, spinners), and testing (smoke/contract scripts).

**Status**
- Not verified; audit `ERP/V2/pages/` and helper modules to ensure the required UX/security behaviors and tests are in place.

### 4.6 Security (`ERP/V2/TODO_SECURITY.md`)

**Scope**
- CSP/rate limits, short-lived tokens with tenant claims, HTTPS/HSTS, no token leakage in URLs/logs, and structured logging for token issuance events.

**Status**
- Not verified; confirm that Streamlit inherits the Django security posture and that tokens are never exposed.

### 4.7 Observability (`ERP/V2/TODO_OBSERVABILITY.md`)

**Scope**
- Streamlit metrics/health endpoints, Django Prometheus counters with `ui=streamlit_v2` tags, traceparent propagation, HTTP client helpers, log fields (`tenant_id`, `ui_channel`), and dashboards for V2 traffic/errors.

**Status**
- Not verified; ensure metrics, traces, and logs include the expected labels and that dashboards/alerts exist.

### 4.8 Deployment (`ERP/V2/TODO_DEPLOY.md`)

**Scope**
- Docker Compose service with healthcheck, Streamlit requirements/env vars, reverse proxy mapping with optional auth_request, optional `/V2/` landing redirect, CSP adjustments, and CI/CD artifact verification.

**Status**
- Not verified; review the deployment manifests to confirm the Streamlit service is orchestrated as described.

### 4.9 Checkpoints (`ERP/V2/TODO_CHECKPOINTS.md`)

**Scope**
- Milestone acceptance criteria (M0 skeleton, M1 auth/tenancy, M2 analytics, M3 vouchers, M4 security/performance, M5 observability, M6 CI/CD).

**Status**
- Not verified; run the checklist against `/V2` to confirm each milestone's SLA/test requirements.

## 5. Finance Module Planning Notes (former `Docs/finance_module_plan.md` & `plantodo.md`)

**Scope highlights**
- The finance module expansion plan captured overarching next steps (regression suites, COA/tax/payment-term setup, permission/training rollout, and submission/reconciliation documentation) as well as the `plantodo.md` checklist that summarized operational follow-ups.

**Status**
- Completed: The detailed guidance from `Docs/finance_module_plan.md` and `plantodo.md` has now been consolidated here, so those file-level artifacts are being retired. All remaining action items referenced in that plan are now tracked earlier in this register (sections 1–3).

**Next steps**
- Continue using this register for tracking; when new finance-phase plans emerge, add them here before removing their standalone files so history stays visible.

## Closing notes
- The preceding sections replace the deleted markdown TODO files. Update this reference when tasks finish or when new follow-up work appears.
- If any of the deleted TODO docs need to be restored for archival reasons, I can reconstruct their text from version history or expand this register further.
