# Voucher Config — UI Guidelines & Widgets

## Existing Design System

Himalytix front-end uses HTMX + Alpine.js with Tailwind CSS for responsive, reactive interfaces. All voucher forms must extend the shared `form_base.html` (provides sticky action bar, keyboard shortcuts, dirty-state tracking and named blocks: `header`, `form_fields`, `actions`). List pages extend `list_base.html` for filters, tables and export tools.

Design tokens (Tailwind classes) must be used for spacing, colors and typography.

## Reusable Widgets & Lookups

We standardize HTMX-enabled, partial-driven lookup widgets:

- Vendor / Supplier Lookup: searchable modal or dropdown; reuse `accounting/partials/vendor_summary.html` where possible. If missing for an org, create `VendorSummaryHXView` and a `/lookup/vendor/` HTMX endpoint.
- Customer Lookup: similar to vendor lookup; create `/lookup/customer/` if not present.
- Item/Product Lookup: autocomplete or modal for selecting stock items; reuse inventory item lists/partials.
- Account Lookup: existing account modal (select account) should be reused for any `account` field.
- Dimension Selectors: cost center, department, project — implement standardized dropdown/typeahead components.
- Currency/Exchange/Payment Terms: reuse purchase invoice components where present.
- Agent/Salesperson Lookup: implement if required by sales vouchers.

Each widget should expose:
- HTMX endpoint returning a partial with search results
- A small JS/Alpine hook to accept a selection and populate the host form
- Accessibility-friendly keyboard navigation and ARIA attributes

## HTMX Patterns

- Line add/remove: `/voucher-config/add-line/` pattern returning a single-row partial
- Validation: `/voucher-config/validate/` returns 422 with field errors rendered into the form
- Recalc: `/voucher-config/recalc/` updates totals partial
- Draft save: `/voucher-config/draft/` does atomic draft persistence and returns updated header/lines
- Post: `/voucher-config/post/` triggers posting orchestrator and returns process tracker updates

All endpoints must return partials (no full-page redirects) so the page state is preserved.

## Voucher Types & UI Blueprint (Purchasing-focused)

We will follow the Purchase Invoice template as canonical and adapt for related vouchers.

- Purchase Order (PO): Header (Vendor, PO No, PO Date, Currency, Payment Terms). Lines (product, description, qty, unit price, discount, tax, account). HTMX add-row, totals, advanced toggle for notes.
- Goods Receipt (GR): Header (Linked PO readonly, Receipt No, Receipt Date, Warehouse). Lines source from PO, include received qty, batch/serial, QC status.
- Purchase Invoice (PI): Header (Vendor, Invoice No, Date, Due Date, PO ref). Lines same as PO. Totals, tax breakdown, dimensions.
- Credit / Debit Notes: Reuse PI with `mode` flag to switch signs and labels.
- Purchase Return: Similar to GR/PI depending on flow; lines subtract from stock and post reversals.
- Landed Cost: Header (Invoice/PO ref, LC Date). Lines allocate landed cost to items with "Landed Cost Amount" column.

Each voucher form must support UDF injection (header/line) and an "Advanced" toggle (dimensions, tax details, UDFs).

## Scaffold Outline (Files to add per voucher)

Example: Purchase Order (ERP/purchasing/)
- `views_po.py`: `POListView`, `POCreateView`, `POUpdateView`, `PODetailView`, `POLineAddView` (HTMX)
- `forms.py`: `PurchaseOrderForm`, `PurchaseOrderLineForm` (line prefix `lines`)
- Templates: `templates/purchasing/purchase_order_form.html` (extends `form_base.html`), `templates/purchasing/partials/purchase_order_line_row.html`
- Static: optional `static/purchasing/js/purchase_order.js` for client-side helpers
- URLs: entries in `purchasing/urls.py`

Repeat similar structure for GR, PI, Landed Cost, Returns.

## Reusability Matrix (high level)

Widget  | PO | GR | PI | PCN | PR | LC
--------|----|----|----|-----|----|---
Vendor  | ✓  | ✓  | ✓  | ✓   | ✓  | ✓
Customer|    |    |    |     |    |   
Item    | ✓  | ✓  | ✓  | ✓   | ✓  | ✓
Account |    | ✓  | ✓  | ✓   |    | ✓
Dimensions| ✓| ✓  | ✓  | ✓   | ✓  | ✓
Currency| ✓  |    | ✓  |     |    | ✓

(Use existing components when marked `(existing)` in codebase.)

## Recommendations & Utilities

- Create a `VoucherFormMixin` to centralize form + formset setup, validation and line handling.
- Implement `GenericAddLineView` that delegates to voucher-specific partial renderers.
- Provide a small JS helper module for currency formatting and row/total recalculation; prefer server calc for authoritative totals and use JS to mirror UX instantly.
- Build an `Alpine` toggle component for showing/hiding advanced sections.
- Keep business logic in services (e.g., `GoodsReceiptService`, `PurchaseInvoiceService`) and keep views thin.

## Testing & Documentation

- Unit tests for each `resolve_ui_schema()` behavior and UDF injection.
- Integration tests ensuring HTMX partials return expected fragments and preserve form state.
- Add UI screenshots and quick start in this document for front-end engineers.

## Implementation Checklist (quick)

- [ ] Create `UI_GUIDELINES.md` (this file)
- [ ] Implement lookup HTMX endpoints for vendor/customer/item if missing
- [ ] Scaffold PO/GR/PI forms and views using `form_base.html`
- [ ] Add unit and integration tests
- [ ] Add admin pages for configuring voucher schemas and UDFs

---

Reference: follow the HTMX/Alpine patterns already present across the repo and reuse existing lookup partials when possible.
