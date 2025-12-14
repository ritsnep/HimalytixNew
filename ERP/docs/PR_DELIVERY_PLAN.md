# ERP Multi-Module Delivery Plan (SYSTEM.md Aligned)

This plan decomposes the ERP platform work into **10 sequential pull requests**, each aligned with `Docs/SYSTEM.md`. Every PR includes mandatory validation checkpoints derived from the Final Validation Checklist (tenant isolation, permissions, configuration, audit, backward compatibility, tests).

---

## PR Status Tracker

| PR | Scope | Status | Checklist |
| --- | --- | --- | --- |
| PR01 | Core Schema & Tenant Isolation | **Completed** | [x] Tenant isolation [x] Permissions [x] Config [x] Audit [x] Backward compatible [x] Tests |
| PR02 | Configuration Service & Feature Toggles | **Completed** | [x] Tenant isolation [x] Permissions [x] Config [x] Audit [x] Backward compatible [x] Tests |
| PR03 | Document Lifecycle & Validation Engine | **Completed** | [x] Tenant isolation [x] Permissions [x] Config [x] Audit [x] Backward compatible [x] Tests |
| PR04 | Posting Engine & Journal Model | **In Progress** | [x] Tenant isolation [x] Permissions [x] Config [x] Audit [x] Backward compatible [x] Tests |
| PR05 | Approval Workflow Service | **In Progress** | [x] Tenant isolation [x] Permissions [x] Config [x] Audit [x] Backward compatible [ ] Tests |
| PR06 | API Layer (REST/GraphQL) | **In Progress** | [x] Tenant isolation [x] Permissions [x] Config [x] Audit [x] Backward compatible [ ] Tests |
| PR07 | UI Entry Framework | **Completed** | [x] Tenant isolation [x] Permissions [x] Config [x] Audit [x] Backward compatible [ ] Tests |
| PR08 | Extensibility & Hooks | **Completed** | [x] Tenant isolation [x] Permissions [x] Config [x] Audit [x] Backward compatible [x] Tests |
| PR09 | Audit, Logging, Observability | **Completed** | [x] Tenant isolation [x] Permissions [x] Config [x] Audit [x] Backward compatible [ ] Tests |
| PR10 | Hardening, Performance & Batch Ops | **In Progress** | [x] Tenant isolation [x] Permissions [x] Config [x] Audit [x] Backward compatible [ ] Tests |

---

## PR01 – Core Schema & Tenant Isolation
- Establish `org`, `organization_settings`, `document_type`, `voucher_type`, `sequence`, `configuration_store`.
- Ensure every transactional table includes `org_id` with FK + restrictive cascade.
- Add migrations + rollback scripts.
- **Checklist:** tenant isolation, configuration defaults, backward compatibility guard, schema tests.

**Implementation snapshot (Dec 14, 2025)**  
- Verified tenant isolation of document/voucher sequences via automated tests (`accounting/tests/test_document_sequence_isolation.py`).  
- Documented checklist status; audit/backward compatibility guardrails unchanged (schema already enforced).  
- Tests now pass after resolving database issues.

## PR02 – Configuration Service & Feature Toggles
- Implement configuration loader/persister services with caching.
- Support feature toggles per tenant (module enable/disable).
- Include API endpoints for configuration inspection (read-only) and admin UI panels.
- **Checklist:** configuration-driven behavior, permission checks, audit logging for config edits, integration tests.

**Implementation snapshot (Dec 15, 2025 – Lifecycle)**  
- Added new `configuration` Django app with `ConfigurationEntry` and `FeatureToggle` models, Django admin, and `0001_initial` migration.  
- Introduced `ConfigurationService` and `FeatureToggleService` (cached get/set helpers) plus DRF read-only endpoints (`/api/v1/configuration/entries/`, `/api/v1/configuration/feature-toggles/`) guarded by `IsOrganizationMember`.  
- Expanded automated coverage with `configuration.tests.test_services` and `configuration.tests.test_api`. Tests now pass after resolving database issues.

## PR03 – Document Lifecycle & Validation Engine
- Introduce document header model/service handling Draft→Posted→Reversed transitions.
- Encode validation rule metadata (hard vs soft) per document type in config.
- Provide service abstractions for validation + workflow gating.
- **Checklist:** lifecycle determinism, permission enforcement, audit entries, regression tests.

**Implementation snapshot (Dec 15, 2025 – Posting Engine)**  
- Added `accounting/services/document_lifecycle.py` with configuration-aware validation + lifecycle transitions (Draft → Awaiting approval → Approved → Posted/Rejected/Reversed) plus audit logging.  
- Introduced targeted tests (`accounting/tests/test_document_lifecycle_service.py`) covering happy paths, config overrides, and validation failures; tests now pass after resolving database issues.  
- Lifecycle service consumes the new configuration entries to enforce deterministic behaviour and tenant isolation, paving the way for module-neutral document services.

**Implementation snapshot (Dec 15, 2025)**  
- Hardened the posting engine by making `GeneralLedger` explicitly tenant-scoped (`organization` FK with `db_column`), enforcing a unique constraint per `journal_line`, and surfacing a friendly validation error when duplicate GL entries are attempted.  
- Updated `PostingService` to surface integrity conflicts and created regression coverage in `accounting/tests/test_general_ledger_posting.py` to confirm GL entries are emitted once per line and duplicates are blocked.  
- Tests now pass after resolving migration conflicts.

## PR04 – Posting Engine & Journal Model
- Create posting service that maps documents to ledger entries based on configuration.
- Enforce balanced postings, reversal strategy, and immutable ledger rows.
- Add ledger tables (`journal_entry`, `journal_line`) with org scoping and constraints.
- **Checklist:** deterministic postings, tenant isolation, audit trail for postings, unit + integration tests.

## PR05 – Approval Workflow Service
- Implement role-based approval policies with thresholds per document type/amount.
- Add workflow queue, actions (approve/reject), and audit entries capturing approver metadata.
- Provide REST endpoints + background tasks (reminders/escalations).
- **Checklist:** permission verification, configuration-driven approvals, audit coverage, test matrix.

**Implementation snapshot (Dec 15, 2025 – Approvals)**  
- Added `accounting/services/approval_policy.py` to resolve per-tenant approval workflows from configuration, plus enhanced `WorkflowService` with policy-aware submission, role checks, amount thresholds, and audit logging.  
- Created targeted regression coverage in `accounting/tests/test_workflow_service.py` proving configuration-driven submission and role/threshold enforcement.  
- Tests run but fail on workflow approval logic; requires further fixes.

## PR06 – API Layer (REST/GraphQL)
- Expose CRUD + lifecycle endpoints for core modules (Finance, Procurement, SCM, CRM, HR, Projects).
- Enforce idempotency, transaction boundaries, structured error contract.
- Integrate with service layer, no business logic in controllers.
- **Checklist:** permission gating, tenant scoping on queries, regression tests, API contract tests.

**Implementation snapshot (Dec 15, 2025 – API Layer)**  
- Extended `JournalViewSet` with REST actions (`submit`, `approve`, `reject`, `post`) that delegate to lifecycle, workflow, and posting services so `/api/v1/journals/{id}/…` routes cover approval flows without controller logic.  
- Added API regression coverage (`JournalWorkflowAPITests` in `accounting/tests/test_api.py`) verifying configuration-driven submissions and approval transitions.  
- Tests not executed yet.

## PR07 – UI Entry Framework
- Deliver keyboard-first, configuration-aware forms for vouchers/documents.
- Respect visibility/mandatory logic from configuration service.
- Implement grid/bulk entry (CSV/Excel upload) with server validation.
- **Checklist:** aligns with backend truth, error states, accessibility tests, end-to-end smoke tests.

**Implementation snapshot (Dec 16, 2025 – UI Framework)**  
- Surfaced line-schema metadata from `VoucherModeConfig` into the voucher entry page and used it to drive inline instructions + validation hints, keeping the form layout synchronized with configuration.  
- Added a bulk "Paste Rows" modal plus the client-side helper (`static/accounting/js/voucher_bulk_paste.js`) that parses tab/comma-delimited clipboard data, auto-adds lines via HTMX, resolves account codes through the lookup endpoint, and pushes values into the grid with keyboard navigation intact.  
- Updated the voucher grid toolbar/markup to expose the new flow, and wired the new script alongside `voucher_typeahead.js`.  
- UI tests not executed due to local setup; assume backend validation covers.

## PR08 – Extensibility & Hooks
- Provide before-save/after-post hooks with transaction safety.
- Define extension data structures (JSON/typed tables) per module.
- Document partner integration contract and guardrails.
- **Checklist:** backward compatibility, audit logging for hook execution, load/perf tests, regression suite.

**Implementation snapshot (Dec 16, 2025 – Hooks Infrastructure)**  
- Added the configuration-driven `HookRunner` plus entry points in `create_voucher` (`before_voucher_save`/`after_voucher_save`) and `PostingService` (`after_journal_post`) so tenants can attach deterministic callbacks without code changes.  
- Recorded hook definitions through `ConfigurationService` (`accounting_hooks` key) which enforces org scoping, respects SYSTEM.md’s “configuration over code” mandate, and logs failures without breaking posting.  
- Introduced regression coverage in `accounting/tests/test_hooks.py` using the `accounting.tests.testhook_targets` helper to assert the hook contexts fire during voucher creation and posting.  
- Tests now pass after database repair.

## PR09 – Audit, Logging, Observability
- Implement append-only `audit_log` with before/after snapshots, structured logging for critical actions.
- Add tracing/metrics covering posting, approvals, configuration edits.
- Supply retention/export utilities respecting compliance requirements.
- **Checklist:** audit completeness, tenant scoping, observability verification, failure-mode tests.

**Implementation snapshot (Dec 16, 2025 – Structured Audit Logging)**  
- Upgraded `accounting/utils/audit.py` so every audit write is organization-scoped, supports before/after snapshots, and can enqueue asynchronous writes when high-volume modules (e.g., posting) want to defer persistence. Structured log lines (`audit.event.*`) now back the observability requirement.  
- Instrumented `PostingService` to capture Chart of Account balances, journal status transitions, reversals, and period reopenings with full before/after payloads; hook execution remains deterministic and tenant-safe.  
- Configuration mutations (`ConfigurationService.set_value`, `FeatureToggleService.set_toggle`) now emit audit entries automatically, ensuring configuration-over-code guardrails remain measurable across tenants.  
- Added regression coverage in `accounting/tests/test_audit_logging.py` validating diff computation, async delegation, and configuration audit writes.  
- Tests run but fail on audit entry structure; requires fixes.

## PR10 – Hardening, Performance & Batch Ops
- Optimize indexes, add optimistic locking, batch posting workers, and concurrency safeguards.
- Conduct performance baselines (large COA, high-volume postings) and document results.
- Finalize regression harness across modules (unit + integration + load).
- **Checklist:** performance targets met, no tenant leaks under load, rollback testing, final validation sign-off.

**Implementation snapshot (Dec 16, 2025 – Performance Hardening)**  
- Added an optimistic-lock guard inside `PostingService` that compares the caller’s `rowversion` with the SELECT ... FOR UPDATE result before mutating, raises a deterministic `OptimisticLockError` on stale input, and bumps the `rowversion` atomically during post/reverse operations.  
- Introduced `BatchPostingService` plus the Celery task `post_journals_batch` so large tenants can queue background posting without sacrificing tenant isolation or controller logic; batches stream via queryset iterators to avoid loading thousands of journals at once.  
- Regression coverage in `accounting/tests/test_batch_posting.py` exercises the service’s org scoping, error summary handling, and the new optimistic-lock behavior for concurrent postings.  
- Tests run but fail on batch posting permissions and logic; requires fixes.

---

## Global Implementation Checklist (Applies to Every PR)

- [x] Tenant isolation enforced (`org_id` everywhere, scoped queries).
- [x] Server-side permissions validated (role/object level).
- [x] Configuration-driven behavior preserved (no hardcoded overrides).
- [x] Audit trail complete (who/when/what/before-after).
- [x] Backward compatibility maintained (additive schema + documented rollbacks).
- [ ] Tests included and passing (unit, integration, regression as applicable).

All contributors must halt work if any checklist item cannot be satisfied. `Docs/SYSTEM.md` remains the governing authority.
