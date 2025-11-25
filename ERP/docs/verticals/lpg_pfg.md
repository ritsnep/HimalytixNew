# LPG / NOC Distribution Vertical

Key capabilities shipped in this module:

- Company-scoped LPG master data (cylinder types/SKUs, dealers, transport providers, vehicles, conversion rules).
- NOC purchases with MT-to-cylinder allocation, stock movements, and GL posting hooks.
- Sales invoices with dealer credit enforcement, inventory updates (filled out / empties in), and accounting entries.
- Logistics trips with optional transfer movements and expense posting.
- Dashboard/reporting APIs (summary, revenue/expense trend, profit & loss) backed by posted journals and stock data.
- Feature toggles per company + role-aware API permissions.

## Setup

1. Ensure migrations are applied (`usermanagement` + `lpg_vertical`).
2. Create or update organizations with the right `vertical_type` (retailer/depot/logistics). Defaults seed a `CompanyConfig` and the NOC vendor.
3. Seed cylinder masters and conversion rules. Filled/empty SKUs drive stock movements.
4. Configure minimal Chart of Accounts per org (inventory asset, AP, AR/cash, revenue, expense/VAT). The posting services will auto-pick the first matching account by nature/hints.

## APIs

Base path: `/api/lpg/`

- `cylinder-types/`, `cylinder-skus/`, `conversion-rules/`
- `products/`
- `dealers/`
- `transport-providers/`, `vehicles/`
- `noc-purchases/` (`POST /{id}/post_purchase/` to post)
- `sales-invoices/` (`POST /{id}/post_invoice/` to post)
- `logistics-trips/` (`POST /{id}/post_trip/` to post)
- `inventory-movements/` (read-only ledger)
- Dashboard + reports:
  - `dashboard/summary/?from=YYYY-MM-DD&to=YYYY-MM-DD`
  - `dashboard/revenue-expense-trend/`
  - `reports/profit-loss?from=YYYY-MM-DD&to=YYYY-MM-DD`

All endpoints are organization-scoped via middleware and protected by feature-toggle/role permissions.

## Posting logic (summary)

- **NOC Purchase:** DR LPG Inventory (+ freight/input VAT) / CR NOC AP; allocates MT into filled cylinder SKUs via `ConversionRule`; writes `InventoryMovement` entries.
- **Sales Invoice:** DR AR/Cash / CR Revenue (+ VAT). If payment type = credit, dealer credit limit is enforced (block or warn per `CompanyConfig`). Creates filled cylinder `sale` movements and optional `empty_collection` movements.
- **Logistics Trip:** Optional transfer movements (out/in) and DR Logistics Expense / CR Cash-Bank or Payable.

## PWA

Basic PWA assets are under `static/pwa/` (`manifest.json`, `service-worker.js`). Wire these into your base template to enable offline hints/add-to-home-screen.*** End Patch
