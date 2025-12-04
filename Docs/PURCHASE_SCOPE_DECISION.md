# Purchase Module: Scope Decision

**Project:** Himalytix ERP  
**Module:** Purchase / Procurement  
**Decision Date:** December 4, 2025  
**Decided By:** Product + Tech Leads

---

## Scope Decision

**Chosen Option:** ✅ Option A – Full Procurement MVP (executed)

**Rationale:** PO + GR + Invoice workflows with matching, GL + inventory posting, and landed costs are now implemented under `ERP/purchasing`. Remaining effort is operational polish (permissions, reconciliation/reporting, performance/UAT, docs/API).

**Start Date:** December 2025 (Phase 1 complete)  
**Target Completion:** January 2026 (Phase 2 polish)

**Key Stakeholders:**
- Product Owner: Approved
- Tech Lead: Approved
- Finance User: Approved

**Sign-off:**
- [x] Product Owner approved
- [x] Finance approved
- [x] Development team approved

---

## Implementation Status (Option A)

### Phase 1: Foundation (Weeks 1-2)
- [x] Model creation: `PurchaseOrder`, `GoodsReceipt`
- [x] Migrations & schema
- [x] Services: `create_purchase_order()`, `receive_goods()`, `post_goods_receipt()`
- [x] API/endpoints (CRUD + actions)

### Phase 2: UI (Weeks 3-4)
- [x] PO list & form (HTMX workspace)
- [x] GR list & form (HTMX workspace)
- [x] Invoice update (link PO/GR)
- [x] Workspace layout

### Phase 3: Integration (Weeks 5-6)
- [x] GL posting service updates (provisional on GR, final on invoice)
- [x] Inventory sync on GR post
- [x] 3-way match validation helpers
- [ ] Reporting & variance views (pending)

### Phase 4: Testing & Polish (Week 7)
- [x] Integration tests (PO + GR + Invoice flows)
- [ ] User acceptance testing
- [ ] Performance tuning
- [ ] Documentation refresh (API + user/dev)

---

## Rollback Plan
1. Revert to Option B (invoice-only) if needed.
2. Hide PO/GR UI and routes (keep models/migrations intact).
3. Document lessons learned and next steps before re-enabling.
