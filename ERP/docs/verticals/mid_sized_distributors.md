# Mid-Sized Distributor Go-Live Playbook
## Phase 1 – Discovery
- Map demand channels, regional warehouses, credit controls.
- Capture pricing tiers, MOQ rules, drop-ship partners.

## Phase 2 – Data Preparation
- Cleanse product masters with UOM, barcode, tariff, reorder data.
- Normalize customer/vendor hierarchies by sales territory.
- Import opening balances into Chart of Accounts and inventory ledger snapshots.

## Phase 3 – Configuration
- Enable multi-price lists, credit-limit enforcement, and serialized tracking.
- Set warehouse/location tree, transit virtual warehouses, and approval routes.
- Configure fulfillment statuses, shipping carriers, and EDI/API connectors.

## Phase 4 – Integration & Automation
- Sync CRM for opportunity-to-order, connect freight APIs, and push invoices to tax gateways.
- Schedule Celery jobs for procurement suggestions and replenishment alerts.

## Phase 5 – Pilot
- Run parallel cycle with two fulfillment centers, validate pick/pack/ship KPIs.
- Stress-test backorders, returns, and RMA workflows.

## Phase 6 – Rollout
- Train customer service, inventory control, and finance teams on tailored dashboards.
- Cut over region by region with rollback checkpoints.

## Phase 7 – Post Go-Live
- Monitor DIFOT, turns, and ATP accuracy; tune safety stock and pricing ladders.