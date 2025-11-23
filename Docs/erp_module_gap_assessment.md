# ERP Gap Assessment – Remaining Work

Use this as the running backlog of what still needs to be delivered to close ERP gaps and reach production readiness.

## Functional modules to build next
- [x] **HR & Payroll**: Department/position/employee/payroll-cycle models exist (`enterprise.models`); still need leave/benefits, attendance, payroll runs, and statutory filings.
- [~] **Fixed Assets**: Asset register/categories/depreciation schedules now have CRUD UI; still need acquisition/disposal postings and depreciation run automation.
- [x] **Manufacturing & Supply Chain**: BOMs, work orders, and material issues exist with CRUD UI; add routings, MRP/MPS, vendor RFQs/scorecards, and maintenance scheduling.
- [x] **CRM & Sales Pipeline**: Leads/opportunities with basic fields are in place; add activities, campaigns/lists, forecasting, and marketing automation hooks.
- [x] **Budgeting & Forecasting**: Budget headers/lines exist in accounting + enterprise; add forecasting, revisions/versions, commitment tracking, and variance analysis UX.
- [x] **Localization & Tax**: Tax authorities/types/codes/rules exist; still need locale tables, region-specific e-invoicing formats, and multi-language label support.
- [x] **Workflow & Approvals**: Approval workflows/steps/tasks exist in accounting; wire into all vouchers/requisitions/journals with delegation/escalation.
- [x] **Integrations & Connectors**: Integration events/endpoints exist; build concrete POS, bank feed/payment gateway, e-commerce/EDI/webhook connectors.

## Production readiness still pending
- [ ] **Data migration/import/export**: CSV/Excel importers with validation, migration scripts for balances/customers/inventory, scheduled exports/backups, BI-friendly feeds.
- [x] **Security & compliance**: Hardened auth/rate limiting and security middleware exist; add MFA enforcement, field-level encryption, GDPR-aligned retention/deletion, and stronger secrets management.
- [ ] **Observability**: Prometheus instrumentation is enabled; add dashboards/alerts for postings, background jobs, integrations, and anomaly flags on financial discrepancies.
- [ ] **Performance & testing**: Core unit/API tests exist; add end-to-end coverage on major flows, load tests on large ledgers/bulk imports, and CI/CD gates for coverage/perf budgets.
- [ ] **User experience**: Base HTMX/Streamlit UI exists; add onboarding helpers, inline guidance, configuration wizards, and tutorials for non-technical users.

## Sequencing suggestions
- Lock target industries and prioritize module order accordingly (e.g., manufacturing vs. services).
- For each module: define data model → API contracts → UI flows → seed data → acceptance tests → migration/import stories.
- Pull approval workflows and external integrations earlier in the roadmap to unblock regulated deployments.
