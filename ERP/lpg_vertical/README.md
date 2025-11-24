# LPG Vertical Django App Patch (NOC Gas Distribution)

This is a **drop-in Django app** called `lpg_vertical` that provides:

- Base models for LPG cylinder types, conversion rules, NOC purchases and logistics trips.
- A ready-made dashboard UI (adapted from your existing `dashboard lpg.html`).
- Service-layer stubs showing where to integrate with your **existing inventory and accounting backends**.

It is intentionally lightweight and non-invasive; you are expected to wire it
into your real ERP engine (vouchers, GL, stock) at your own pace.

---

## 1. Folder Structure

```
lpg_vertical/
  __init__.py
  apps.py
  models.py
  services.py
  views.py
  urls.py
  templates/
    lpg_vertical/
      dashboard.html
  static/
    lpg_vertical/
      js/
      css/
  README.md
```

---

## 2. How to Install into Your Existing Project

### Step 1 – Copy the app

Copy the entire `lpg_vertical` folder into the root of your Django project
(alongside your existing apps).

Example:

```
your_project/
  config/
  accounting/
  inventory/
  ...
  lpg_vertical/
```

### Step 2 – Add to `INSTALLED_APPS`

In your Django settings (e.g. `settings.py` or `config/settings/base.py`):

```python
INSTALLED_APPS = [
    # ...
    "lpg_vertical.apps.LpgVerticalConfig",
]
```

### Step 3 – Include URLs

In your main `urls.py` (project-level):

```python
from django.urls import include, path

urlpatterns = [
    # ...
    path("lpg/", include("lpg_vertical.urls")),
]
```

This will expose:

- `/lpg/dashboard/`
- `/lpg/api/dashboard-summary/`
- `/lpg/api/noc-purchases/`
- `/lpg/api/logistics/`

### Step 4 – Run migrations

Generate and apply migrations for the new models:

```bash
python manage.py makemigrations lpg_vertical
python manage.py migrate
```

You will now have tables for:

- `CylinderType`
- `CylinderSKU`
- `ConversionRule`
- `NocPurchase`
- `LogisticsTrip`

### Step 5 – Open the LPG dashboard

Start your server:

```bash
python manage.py runserver
```

Navigate to: `http://localhost:8000/lpg/dashboard/`

You should see the LPG dashboard UI with static demo numbers and charts.

---

## 3. Integrating with Your Existing Inventory & Finance

The **key design** of this patch is that it does *not* assume anything about
your current ERP tables. Instead, you get explicit "hook" functions in
`lpg_vertical/services.py` that you can adapt.

### 3.1. NOC purchase → vouchers, GL & stock

Open `lpg_vertical/services.py` and look at:

```python
def post_noc_purchase(noc_purchase: NocPurchase) -> None:
    ...
```

Implementation idea inside your project:

1. **Create or link a purchase voucher** in your existing purchasing module:
   - Vendor = NOC (from your vendor master).
   - Lines:
     - LPG bulk (quantity MT × rate_per_mt).
     - Transport cost.
     - Tax amount.

2. **Post GL entries** using your current accounting services:
   - DR: LPG Inventory (asset).
   - DR: Freight/Transport (expense or capitalized into inventory).
   - DR: Input VAT (if applicable).
   - CR: NOC Accounts Payable.

3. **Update inventory** using your existing inventory service:
   - Use `allocate_mt_to_cylinders` to convert the MT into per-cylinder counts.
   - Call your stock increment functions to update filled cylinder stock.

4. **Mark NocPurchase as posted**:
   - Set `noc_purchase.status = NocPurchase.STATUS_POSTED`.
   - Optionally store a OneToOne link to your voucher record.

The function currently raises `NotImplementedError` to force you to decide
how to integrate with your exact DB schema.

### 3.2. Logistics trip → stock transfers & expense

Look at:

```python
def post_logistics_trip(trip: LogisticsTrip) -> None:
    ...
```

Implementation idea:

1. Call your existing inventory transfer function to move cylinders from
   `trip.from_location` to `trip.to_location` (if you track locations).

2. Create a GL entry for the logistics cost:
   - DR: Logistics / Freight Out expense.
   - CR: Cash/Bank or Transport Payable.

Again, this is left as a stub for you to wire into your own ERP layer.

---

## 4. Using the Dashboard Data APIs

Out of the box, the dashboard view uses **static JS demo data**.

You have three helper APIs ready to be replaced with real logic:

- `/lpg/api/dashboard-summary/`
- `/lpg/api/noc-purchases/`
- `/lpg/api/logistics/`

They currently:

- Return hard-coded KPIs (for quick UI verification).
- Serialize the last few `NocPurchase` and `LogisticsTrip` records.

### How to connect to your real engine

You can edit `views.py`:

- Replace the constants in `api_dashboard_summary` with real aggregations
  over your accounting and inventory tables.
- Make sure `NocPurchase` is updated whenever you perform a real NOC purchase.

---

## 5. Multi-Tenant / Company-Level Integration (Optional)

This patch does **not** enforce a Company/Tenant foreign key because
every ERP has different patterns. Recommended approach:

1. Once you decide which model represents company/tenant
   (e.g. `Company`, `CostClass`, `Branch`), add an FK to:
   - `CylinderType`
   - `CylinderSKU`
   - `ConversionRule`
   - `NocPurchase`
   - `LogisticsTrip`

2. Filter all queries in `views.py` by the current company context.

3. Optionally, move company-awareness into a custom middleware or a
   request-scoped helper.

---

## 6. What Is Safe to Change / Extend

You **should feel free** to:

- Add foreign keys to your own `Company`, `Vendor`, `Dealer`, `Location`,
  `Voucher`, `Ledger` models.
- Rename `trip_date` / `purchase_date` fields to match your naming conventions.
- Split `LogisticsTrip` into header/lines if that matches your design.

Just keep the **overall separation**:

- `models.py` — LPG-specific schemas.
- `services.py` — integration hooks into your ERP.
- `views.py` & `templates/` — vertical-specific UI and APIs.

---

## 7. Sanity Checklist After Integration

- [ ] `/lpg/dashboard/` loads with your layout (optional: extend your base).
- [ ] You can create `CylinderType` and `CylinderSKU` records via admin.
- [ ] You can create a `NocPurchase` via admin or a custom form.
- [ ] After implementing `post_noc_purchase`, it:
      - creates a voucher,
      - posts GL entries,
      - updates inventory.
- [ ] Logistics trips are showing in `/lpg/api/logistics/`.
- [ ] No impact on your hospital/clinic/other verticals unless you enable it.

Once this is stable for one depot, you can roll it out tenant by tenant.

---
