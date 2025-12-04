# Purchase Module: Decision Record

**Status:** Option A executed (Full Procurement MVP)  
**Date:** December 4, 2025

---

## Snapshot
- PO + GR + Invoice workflows are live in `ERP/purchasing` with HTMX workspaces, GL + inventory posting, landed costs, and matching helpers.
- Legacy Vendor Bill entry under `accounting/` remains; keep or retire after cleanup.
- Remaining focus: permissions, reconciliation/reporting, performance + UAT, docs/API refresh.

## Why Option A
- Complete procurement visibility (PO → GR → Invoice) with stock impact at receipt time.
- 3-way variance detection available via matching helpers and detail views.
- Aligns with inventory/accounting architecture already in place.

## Next Steps (Phase 2)
1. Finalize roles/permissions for procurement, warehouse, and finance.
2. Ship GL reconciliation + 3-way variance reporting (with export).
3. Run performance/UAT scenarios (partial receipts, tolerance, multi-currency) and record evidence.
4. Refresh API + user/developer docs; deprecate legacy Vendor Bill entry if approved.

## Owners
- **Product/Finance:** Approve permissions + reporting scope; decide on legacy bill entry.
- **Tech Lead:** Oversee legacy cleanup and performance/UAT gate.
- **Developers:** Deliver reconciliation/reporting, permissions seeding, doc/API refresh.
- **QA:** Execute UAT/performance plan and log results.
