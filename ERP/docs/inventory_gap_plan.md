# Inventory Gap Closure Plan

## Context
- The current `inventory` app already provides master data (products, categories, warehouses, batches) plus stock tracking through `InventoryItem`/`StockLedger` (see `inventory/models.py`) and a CSR-friendly dashboard (`inventory/templates/inventory/dashboard.html`).
- Operational workflows rely on `PickPackShipService` (`inventory/services/fulfillment_service.py`) and accounting linkage runs through `InventoryPostingService` in `accounting/services` that currently uses weighted-average costing.
- The README and supporting docs (`Docs/INVENTORY_COMPLETE_IMPLEMENTATION.md`, `Docs/verticals/service_saas_inventory.md`) explicitly call out remaining work around adjustments, transfers, replenishment, reporting enhancements, costing, and permissions.

## Gap Summary
1. **Stock Take / Adjustment** - No dedicated UI/workflow exists for recording physical count variances or scrap adjustments and reconcile with the ledger.
2. **Warehouse Transfers** - Internal transfer flows (pick-issue-receive) are not surfaced in the UI; GL impact needs automation.
3. **Reorder & Forecasting** - Existing product/InventoryItem fields hint at reorder levels, but there is no alerting, replenishment recommendations, or PO drafting assistance.
4. **Barcode & Mobile Support** - Picking/receiving forms lack barcode/QR scanning hooks, and there is no mobile-friendly view for warehouse staff.
5. **Advanced Reporting & Dashboards** - Inventory dashboards are basic tables; visual KPIs/chart widgets (aging, turnover, stock value) are missing.
6. **Costing Methods** - Weighted average is the only method wired in `InventoryPostingService`; organizations need FIFO/LIFO/standard options per item.
7. **Permission Control** - Views still rely on minimal login checks; granular rights (picklist creation, shipment approval, adjustments) are absent.

## Task Breakdown
Each area below is scoped for a multi-step implementation that extends existing services/views while keeping the Tailwind/Crispy UI stack.

### 1. Stock Take & Adjustment Workflow
- **Models/Services**: Add `StockAdjustment` + `StockAdjustmentLine` tied to `InventoryItem`/`StockLedger` and reuse `InventoryPostingService` to persist adjustments (have it expose an `record_adjustment` helper). Track reasons (scrap, damage, correction) and variance.
- **Forms/Views**: Extend `inventory/forms.py` and `inventory/views.py` to include a `StockAdjustmentCreateView` plus `AdjustmentLineFormSet`, mirroring existing receipt/issue forms for consistency.
- **Templates/UX**: Create a template under `inventory/templates/inventory/stock_adjustment_form.html` using existing form card structure. Provide HTMX endpoints (or Crispy modal) so users can start counts by warehouse/location and scan SKUs.
- **Reconciliation & Reports**: Offer a variance report (`inventory/templates/inventory/stock_adjustment_report.html`) summarizing count vs ledger, referencing `StockLedger` data.
- **Tests**: Cover service behavior and view permission/responses in `inventory/tests.py`.

### 2. Inter-Warehouse Transfers
- **Transfer Models**: Introduce `TransferOrder` with `transfer_lines` that reference source/destination warehouses/locations and statuses (`draft`, `issued`, `received`). Leverage `TransitWarehouse` if needed for in-transit posting.
- **Service Workflow**: Build a `TransferService` (or extend `PickPackShipService`) that issues stock from origin and posts receipts to destination via `InventoryPostingService`, ensuring GL entries debit/credit inventory accounts appropriately.
- **Forms/UI**: Add forms in `ERP/inventory/forms.py` and new templates (e.g., `inventory/templates/inventory/transfer_form.html`) to create multi-step transfer orders. Reuse existing list-detail layouts.
- **UI Flows**: Provide list views for transfer orders and ties to `picklist` (for manual prep). Add buttons on warehouse detail screens for initiating transfers.

### 3. Reorder & Forecasting Engine
- **Service**: Implement `ReorderService` that runs off `InventoryItem.reorder_level`, `product.min_order_quantity`, and historical usage (derive from `StockLedger` or delivered `PickList` data). Expose methods to:
  1. Identify items below reorder point.
  2. Suggest quantities (respecting MOQs and safety stock) and preferred vendors.
  3. Auto-create `Requisition`/`PurchaseOrder` skeletons (can be TODO with placeholder models linking to accounting/purchasing apps).
- **UI/Alerts**: Create dashboard widget (e.g., `inventory/templates/inventory/reorder_alerts.html`) that shows flagged SKUs and includes CTA to `create requisition`. Integrate into `inventory/templates/inventory/dashboard.html` with Chart.js or Tailwind cards.
- **Background Tasks**: Add periodic Celery/RQ task stub in `inventory/tasks.py` that runs reorder checks, triggers email/notification, and stores recommendation snapshots (new model `ReorderRecommendation`).

### 4. Barcode & Mobile-Friendly Experiences
- **Frontend**: Add a dedicated `inventory/static/inventory/js/barcode_scan.js` referencing HTMX endpoints to resolve SKUs/locations. Reuse Tailwind forms but optimize for mobile (large buttons, responsive layout).
- **Views/Endpoints**: Provide HTMX/JSON endpoints in `inventory/api/views.py` (e.g., `ScanProductView`, `ScanLocationView`) that return product/location data from barcode. Link to existing templates via `inventory/templates/components/inventory/forms/`.
- **UX**: Create mobile-friendly `inventory/templates/inventory/scanner_form.html` (PWA-ready placeholder) with instructions, scanning area, and inline results list.
- **Testing**: Add API view tests ensuring barcode lookups and permission gating.

### 5. Advanced Reporting & Dashboards
- **Data Prep**: Build query helpers in `inventory/utils.py` (or new `ReportService`) that calculate aging buckets, stock valuation per category, turnover (sales vs on-hand). Reuse `StockLedger` for historical snapshots.
- **Templates**: Enhance `inventory/templates/inventory/dashboard.html` to include Chart.js/Plotly snippets showing:
  - Inventory aging funnel.
  - On-hand value heatmap by warehouse/category.
  - Fast vs slow movers chart referencing ledger movement counts.
  - KPI cards (stock value, turnover, avg days on hand).
- **BI Integration**: Document how to expose these metrics via API/CSV (maybe extend `inventory/api/serializers.py` for report data) for BI consumption.
- **Accessibility**: Ensure charts degrade gracefully; provide data tables and alt text for screen readers.

### 6. Costing Methods Support
- **Model Enhancements**: Add a `costing_method` choice field to `Product` (`weighted_average`, `fifo`, `lifo`, `standard`). Provide optional `standard_cost` and support for multiple layers (maybe `CostLayer` model referencing batches).
- **Posting Service**: Refactor `accounting/services/inventory_posting_service.py` to delegate cost calculation to a new `CostingService`. Each method should compute `unit_cost` differently (FIFO/LIFO from `StockLedger`, standard uses `standard_cost`). Keep weighted average backward-compatible.
- **Configuration UI**: Extend product form (`inventory/forms.py` / template) to allow selecting costing method; surface warnings when switching.
- **Testing**: Add service-level tests validating cost outcomes for each method.

### 7. Permission Control
- **Permissions Model**: Define granular Django `Permission` entries (e.g., `can_create_picklist`, `can_approve_shipment`, `can_post_adjustment`) and ensure relevant views/classes check `permission_required`. Prefer mixins (e.g., `InventoryPermissionMixin`) reused across list/create views.
- **Templates**: Hide/disable UI actions when users lack permissions (check via template tags referencing `request.user.has_perm`).
- **Auditability**: Add metadata (created_by, approved_by) to operational models and surfacing in forms/details.

## Deliverables & Validation
- Create/extend templates, static assets, and forms so the UX follows the existing Tailwind + Crispy layout (see `inventory/templates/inventory/_form_base.html` and component partials).
- Add service/view tests to `inventory/tests.py`/`accounting/tests/test_inventory_integration.py` covering new workflows and permissions.
- Document new endpoints/flows in README and update `Docs/verticals/service_saas_inventory.md` to keep stakeholders aligned.
- Provide migration(s) for new models/fields and ensure data integrity (use `makemigrations` when ready).

## Next Steps
1. Align on scope (which workflows to prioritize) before implementing to avoid overreach.
2. Build and test each area incrementally, verifying ledger/JV impact via existing `InventoryPostingService` wrappers.
3. Update dashboards and documentation only after services are stable so stakeholders know where to look for the new features.
