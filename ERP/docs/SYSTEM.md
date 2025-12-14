# ERP Product Engineering Enforcement Contract

## Purpose

This document defines the non-negotiable engineering operating rules for this ERP product. It is the single source of truth for all technical decisions, code reviews, and architectural choices.

This repository represents a single, long-lived, enterprise-grade ERP system, comparable in discipline to SAP-class products. Every line of code must reflect production-grade quality standards.

### What This Is NOT

- A prototype
- A demo
- A learning project
- A fast-and-loose startup codebase
- A personal experimentation ground

### Core Mandate

All changes must preserve:
- **Correctness** — accurate calculations and data integrity
- **Auditability** — complete traceability of all transactions
- **Configurability** — behavior driven by configuration, not code
- **Backward Compatibility** — existing deployments and data never break

---

## Product Reality Assumptions

Every contributor and AI assistant **MUST** assume:

- **One ERP product, many modules** — not a framework or toolkit
- **Multi-tenant architecture** — tenant isolation is mandatory, not optional
- **Real accounting, real inventory, real audits** — regulatory compliance required
- **Real customers with production data** — downtime and data loss are unacceptable
- **Features must survive years of change** — extensibility without breaking changes
- **Compliance dependencies** — financial, tax, and legal regulations apply

**If any assumption is violated, work must stop immediately and the issue must be escalated.**

---

## Architectural Principles (Enforced)

### 1. Configuration Over Code

- Behavior must be driven by configuration wherever feasible
- Hardcoded logic is allowed **only** when justified and documented in code comments
- UI must reflect configuration; never override or bypass it
- Configuration changes must not require code deployment

### 2. Separation of Concerns

- **Entry** ≠ **Posting** ≠ **Reporting**
- Controllers/views are thin (validation routing only)
- Business rules live in services and domain logic layers
- Database enforces integrity constraints; application code is the second line of defense
- No business logic leakage into UI or HTTP layers

### 3. Backward Compatibility First

- Existing data must never break; deprecation over deletion
- Schema changes require migrations with documented rollback paths
- Defaults must preserve current behavior; opt-in for new behavior
- Version your APIs; never silent breaking changes

### 4. Deterministic Behavior

- Same input + same state → identical result (always)
- No hidden side effects or timing dependencies
- No implicit state mutations
- Idempotent operations where applicable (especially for critical transactions)

---

## Multi-Tenant Enforcement

Tenant isolation is **mandatory**:

**All Tables Must Include Tenant Identity:**
- `org_id` (or equivalent) must exist in:
    - All transactional tables (invoices, orders, shipments)
    - All configuration tables (tax rules, payment terms)
    - All audit logs and change history
    - All reporting views and aggregations

**Query Discipline:**
- Queries **MUST** scope by tenant in WHERE clauses
- Never trust implicit tenant context; always explicit
- Use database constraints to prevent cross-tenant queries

**Permission Enforcement:**
- Permission checks **MUST** enforce tenant boundaries at the service layer
- Verify user's tenant assignment before data access
- Log and alert on unauthorized cross-tenant access attempts

**Violation Protocol:**
- Any tenant data leak is a **critical defect** (P0)
- Must be fixed immediately and audited for scope
- Requires post-incident review

---

## Security & Permissions

### Server-Side Enforcement Only

- **UI permissions are cosmetic** — they improve UX but never provide security
- All authorization decisions must be made server-side
- Never trust client-side permission state

### Authorization Rules

- Role-based access control (RBAC) enforced at service layer
- Object-level access control where applicable
- No silent permission bypasses; explicit deny is safer than implicit allow
- All critical actions require explicit authorization checks

### Sensitive Operations

- Password changes, deletions, financial postings, audit data access
- Must be logged with user identity and timestamp
- Must be reviewable by compliance teams

---

## Document & Transaction Discipline

All transactional documents must define:

| Property | Definition | Example |
|----------|-----------|---------|
| **Lifecycle** | Allowable state transitions | Draft → Posted → Reversed / Cancelled |
| **Validation Rules** | Hard (blocking) vs soft (warning) | Hard: GL account must exist; Soft: unusual exchange rate |
| **Posting Rules** | Side effects and ledger impact | Invoice posting creates AR transaction and GL entries |
| **Reversal Strategy** | How to undo posted transactions | Full reversal with new GL entries (never deletion) |
| **Numbering Rules** | Unique identity & sequence | Sequential invoice numbers per organization per year |
| **Audit Footprint** | Change history and accountability | Who posted it, when, what was changed, why |

**Mutation Rules:**
- No document may mutate posted data silently
- Post-posting changes require explicit reversal + new transaction
- Audit trail must show the reversal and the correcting entry

---

## Data Model Rules

### Design Principles

- **Prefer clarity over cleverness** — readable schema beats optimized obfuscation
- Use database constraints, indexes, and foreign keys
- Avoid over-normalization that complicates queries
- Consider reporting requirements upfront (avoid post-facto redesigns)

### Financial Data Protection

- Never delete financial data; mark as archived/inactive
- Maintain complete audit trail of all changes
- Support ledger reconciliation and year-end closures

### Schema Change Protocol

All schema changes must document:

1. **Why** — business requirement or defect fix
2. **Impact Analysis** — affected tables, views, reports, API contracts
3. **Migration Plan** — data transformation steps, validation queries
4. **Rollback Strategy** — how to safely reverse in production
5. **Testing** — migration tested on production-like dataset sizes
6. **Deployment Window** — downtime or online migration strategy

---

## API & Service Layer Rules

### Design Standards

- **Idempotency** — write operations should be idempotent where applicable (use idempotency keys)
- **Explicit Transactions** — transaction boundaries clear in code and documentation
- **Consistent Error Contracts** — structured error responses (code, message, details)
- **No Business Logic in Controllers** — validation and decisions in service layer
- **Isolation** — services must be testable in isolation; mock external dependencies

### API Versioning

- Version APIs; never silent breaking changes
- Support at least one prior API version during transition
- Document deprecation timelines clearly

---

## UI / UX Rules (ERP-Grade)

### Productivity Over Polish

- **Keyboard-first workflows** — power users work faster with keyboard shortcuts
- **Predictable navigation** — consistent patterns across modules
- **Explicit error states** — never hide errors or fail silently
- **No silent auto-corrections** — if the system fixed your data, you must know it
- **Power-user efficiency over cosmetic polish** — accountants need speed, not animations

### UI-Backend Alignment

- UI must follow backend truth; never display outdated cached data
- Validation rules on UI must match server-side rules exactly
- Permission state on UI must match server authorization decision

---

## Audit & Observability

### Audit Requirements

All critical actions must record:

- **Who** — user identity (not just session ID)
- **When** — precise timestamp (UTC, with millisecond precision)
- **What** — transaction type, affected records, amounts
- **Before/After** — state change details (old value → new value)
- **Why** — reason code or user comment if applicable

### Audit Trail Use Cases

- Support compliance review and regulatory audits
- Enable forensics for financial discrepancies
- Track configuration changes and their impact
- Demonstrate change control to external auditors

### Logging Standards

- Structured logging (JSON or key-value pairs, not free text)
- Meaningful context: user_id, org_id, transaction_id, operation
- Appropriate levels (ERROR for actual failures, INFO for state changes)
- Retention policy aligned with regulatory requirements

---

## Performance & Scalability

### Mandatory Considerations

Every change must assess:

- **Data Volume Growth** — will this query scale to 10M+ records?
- **Query Patterns** — are there N+1 risks? Missing indexes?
- **Batch Operations** — can users process bulk transactions efficiently?
- **Locking and Concurrency** — are there deadlock or contention risks?
- **Integration Load** — can your API handle high-frequency calls?

### Defect Classification

- Performance negligence (missing indexes, N+1 queries) is considered a **defect**, not a "future optimization"
- If a feature is slow at launch, it will remain slow in production

---

## Testing Is Mandatory

### Test Coverage Requirements

Each change must include:

- **Unit Tests** — business rules in isolation (no DB)
- **Integration Tests** — API behavior + database interactions
- **Regression Tests** — protection for known failures and edge cases
- **Edge Case Coverage** — boundary conditions, null handling, decimal precision

### Test Philosophy

- "No tests" means "not done"
- Tests document expected behavior
- Tests protect against future mistakes
- Coverage ≥ 80% for critical paths (accounting, posting, permissions)

---

## Delivery Discipline

### Reviewable Units

Work must be delivered in logical, reviewable chunks:

1. **Schema & Configuration** — DDL changes and config data
2. **Core Services** — business logic and domain models
3. **API Wiring** — controllers and HTTP integration
4. **UI Integration** — frontend changes aligned with API
5. **Hardening & Tests** — edge cases, error handling, tests

**Large, unreviewable changes are rejected outright.** If a PR is >500 lines and touches >5 files, split it.

---

## AI Usage Rules

### AI as a Tool, Not a Decision Maker

AI is treated as:

- **A fast junior engineer** — can code, but needs direction
- **Not an architect** — humans own design decisions
- **Not a source of truth** — humans verify all output
- **A productivity multiplier** — not a replacement for engineering judgment

### Human Ownership

Humans own:

- **Architecture** — system design and trade-offs
- **Product Intent** — feature scope and priorities
- **Quality Bar** — testing, performance, compliance standards
- **Release Approval** — accountability for production impact

### AI Output Validation

- AI output must follow this SYSTEM.md or be discarded
- Engineers must understand and take responsibility for AI-generated code
- Code reviews apply equally to AI and human-written code

---

## Final Validation Checklist (Required)

**Before merging any change, verify all items below:**

- [ ] **Tenant Isolation** — org_id in all tables, queries scoped by tenant
- [ ] **Permissions** — server-side authorization checks present and tested
- [ ] **Configuration-Driven Behavior** — no hardcoded logic without justification
- [ ] **Audit Trail** — critical actions logged with who/when/what/before-after
- [ ] **Backward Compatibility** — existing data and APIs not broken
- [ ] **Tests Included** — unit, integration, and regression tests passing
- [ ] **Schema Migrations** — rollback path documented if applicable
- [ ] **Performance** — no N+1 queries, indexes added, batch operations considered
- [ ] **Documentation** — code comments for non-obvious logic, API contracts clear
- [ ] **Code Review** — at least one other engineer has approved

**If any item fails, the change is incomplete and must not be merged.**

---

## Authority

This SYSTEM.md is the **single source of engineering truth** for this repository.

It overrides:
- Individual preference
- Speed considerations
- Convenience shortcuts
- "Just this once" exceptions

**All disagreements about engineering standards must reference this document.**

---

## Questions or Conflicts?

If you believe a rule in this document is impractical or conflicts with a business requirement, raise an issue with:

- **Context** — what you're trying to build
- **Blocker** — how this rule prevents you from succeeding
- **Proposed Change** — what modification would help
- **Risk Assessment** — what could go wrong if we relax this

Changes to SYSTEM.md are approved by the technical lead and product owner.