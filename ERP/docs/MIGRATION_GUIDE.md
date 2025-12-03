# DATABASE MIGRATIONS GUIDE

## Overview
This guide covers the migration process for the new vertical ERP features.

---

## Prerequisites

1. **Backup your database** before running migrations:
   ```bash
   # SQLite
   cp db.sqlite3 db.sqlite3.backup
   
   # PostgreSQL
   pg_dump erp_db > erp_db_backup.sql
   ```

2. **Ensure virtual environment is activated:**
   ```bash
   # Windows
   .\venv\Scripts\Activate.ps1
   
   # Linux/Mac
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

---

## Migration Sequence

### Phase A: Pricing & Fulfillment Models

**Models Added:**
- Inventory: PriceList, PriceListItem, CustomerPriceList, PromotionRule
- Inventory: TransitWarehouse, PickList, PickListLine, PackingSlip
- Inventory: Shipment, Backorder, RMA, RMALine

**Steps:**
```bash
# Generate migrations
python manage.py makemigrations Inventory

# Review migration file
# File will be in: inventory/migrations/000X_auto_YYYYMMDD_HHMM.py

# Apply migration
python manage.py migrate inventory

# Verify tables created
python manage.py dbshell
# Then run: .tables  (SQLite) or \dt (PostgreSQL)
```

**Expected Tables:**
- inventory_pricelist
- inventory_pricelistitem
- inventory_customerpricelist
- inventory_promotionrule
- inventory_promotionrule_apply_to_products (M2M)
- inventory_transitwarehouse
- inventory_picklist
- inventory_picklistline
- inventory_packingslip
- inventory_shipment
- inventory_backorder
- inventory_rma
- inventory_rmaline

---

### Phase B: Manufacturing Extensions

**Models Added:**
- enterprise: BOMRevision, QCCheckpoint, QCInspectionRecord, NCR
- enterprise: ProductionCalendar, Shift, ProductionHoliday
- enterprise: YieldTracking, WorkOrderCosting

**Steps:**
```bash
# Generate migrations
python manage.py makemigrations enterprise

# Apply migration
python manage.py migrate enterprise
```

**Expected Tables:**
- enterprise_bomrevision
- enterprise_qccheckpoint
- enterprise_qcinspectionrecord
- enterprise_ncr
- enterprise_productioncalendar
- enterprise_shift
- enterprise_productionholiday
- enterprise_yieldtracking
- enterprise_workordercosting

---

### Phase C: Subscription & Service Models

**Models Added:**
- billing: SubscriptionPlan, UsageTier, Subscription, SubscriptionUsage
- billing: SubscriptionInvoice, DeferredRevenue, DeferredRevenueSchedule, MilestoneRevenue
- service_management: All models (new app)

**Steps:**

1. **Add service_management to INSTALLED_APPS:**

Edit `ERP/settings.py` or `dashboard/settings.py`:
```python
INSTALLED_APPS = [
    # ... existing apps ...
    'service_management',
]
```

2. **Create billing migrations:**
```bash
# Create billing/models/__init__.py if it doesn't exist
# Add: from .subscription import *

python manage.py makemigrations billing
python manage.py migrate billing
```

3. **Create service_management migrations:**
```bash
python manage.py makemigrations service_management
python manage.py migrate service_management
```

**Expected Tables (billing):**
- billing_subscriptionplan
- billing_usagetier
- billing_subscription
- billing_subscriptionusage
- billing_subscriptioninvoice
- billing_deferredrevenue
- billing_deferredrevenueschedule
- billing_milestonerevenue

**Expected Tables (service_management):**
- service_management_devicecategory
- service_management_devicemodel
- service_management_devicelifecycle
- service_management_devicestatehistory
- service_management_servicecontract
- service_management_serviceticket
- service_management_warrantypool
- service_management_rmahardware
- service_management_deviceprovisioningtemplate
- service_management_deviceprovisioninglog

---

## Troubleshooting Migrations

### Issue: "No changes detected"
**Solution:**
```bash
# Force migration detection
python manage.py makemigrations --empty Inventory
python manage.py makemigrations --empty billing
python manage.py makemigrations --empty service_management
```

### Issue: Foreign key constraint errors
**Solution:**
- Ensure referenced models exist first
- Check that Organization model is properly imported
- Verify ChartOfAccount references

### Issue: "Table already exists"
**Solution:**
```bash
# Mark migration as applied without running
python manage.py migrate --fake Inventory 000X
```

### Issue: Circular dependencies
**Solution:**
- Run migrations in order: Inventory → enterprise → billing → service_management
- Use `--run-syncdb` if needed:
```bash
python manage.py migrate --run-syncdb
```

---

## Post-Migration Verification

### 1. Check Table Creation
```bash
python manage.py dbshell
```

**SQLite:**
```sql
.tables
.schema inventory_pricelist
```

**PostgreSQL:**
```sql
\dt
\d inventory_pricelist
```

### 2. Test Model Access
```bash
python manage.py shell
```

```python
from inventory.models import PriceList, PromotionRule
from billing.models.subscription import Subscription
from service_management.models import DeviceLifecycle

# Test queries
print(PriceList.objects.count())
print(Subscription.objects.count())
print(DeviceLifecycle.objects.count())
```

### 3. Run Django Check
```bash
python manage.py check
```

### 4. Create Test Data
```bash
python manage.py shell
```

```python
from usermanagement.models import Organization
from inventory.models import PriceList
from billing.models.subscription import SubscriptionPlan
from service_management.models import DeviceCategory

# Get or create organization
org = Organization.objects.first()

# Test price list creation
pl = PriceList.objects.create(
    organization=org,
    code='TEST-001',
    name='Test Price List',
    currency_code='USD',
    is_active=True
)
print(f"Created: {pl}")

# Test subscription plan
plan = SubscriptionPlan.objects.create(
    organization=org,
    code='TEST-PLAN',
    name='Test Plan',
    base_price=29.99
)
print(f"Created: {plan}")

# Test device category
cat = DeviceCategory.objects.create(
    organization=org,
    code='TEST-CAT',
    name='Test Category'
)
print(f"Created: {cat}")
```

---

## Migration Rollback

### Rollback to specific migration:
```bash
# Find migration number
python manage.py showmigrations inventory

# Rollback to previous
python manage.py migrate inventory 0003

# Rollback all
python manage.py migrate inventory zero
```

### Delete migration files:
```bash
# Windows
Remove-Item inventory\migrations\0004_*.py
Remove-Item billing\migrations\0002_*.py
Remove-Item service_management\migrations\0001_*.py

# Linux/Mac
rm inventory/migrations/0004_*.py
rm billing/migrations/0002_*.py
rm service_management/migrations/0001_*.py
```

---

## Data Seeding (Optional)

### Create sample data for testing:

```bash
python manage.py shell
```

```python
from django.utils import timezone
from decimal import Decimal
from usermanagement.models import Organization
from inventory.models import (
    PriceList, PriceListItem, Product, PromotionRule,
    Warehouse, Location
)
from billing.models.subscription import SubscriptionPlan, UsageTier
from service_management.models import DeviceCategory, DeviceModel

org = Organization.objects.first()

# Sample price list
price_list = PriceList.objects.create(
    organization=org,
    code='RETAIL-2025',
    name='Retail Pricing 2025',
    currency_code='USD',
    is_active=True
)

# Sample subscription plan
plan = SubscriptionPlan.objects.create(
    organization=org,
    code='BASIC-M',
    name='Basic Monthly',
    plan_type='recurring',
    billing_cycle='monthly',
    base_price=Decimal('29.99'),
    trial_period_days=14
)

# Usage tier
UsageTier.objects.create(
    subscription_plan=plan,
    tier_name='Included',
    min_quantity=0,
    max_quantity=1000,
    price_per_unit=0
)

# Device category
device_cat = DeviceCategory.objects.create(
    organization=org,
    code='ROUTERS',
    name='Network Routers'
)

print("Sample data created successfully!")
```

---

## Performance Optimization

### Add Indexes (Already in Models)
The models include index definitions. Verify they were created:

```bash
python manage.py sqlmigrate inventory 0004
```

### Analyze Tables (PostgreSQL)
```sql
ANALYZE inventory_pricelist;
ANALYZE inventory_shipment;
ANALYZE billing_subscription;
ANALYZE service_management_devicelifecycle;
```

### Create Additional Indexes (if needed)
```python
# In migration file
operations = [
    migrations.RunSQL(
        "CREATE INDEX idx_subscription_billing ON billing_subscription(next_billing_date, status);"
    ),
]
```

---

## Production Deployment Checklist

- [ ] Backup production database
- [ ] Test migrations on staging environment
- [ ] Review generated SQL with `sqlmigrate`
- [ ] Schedule maintenance window
- [ ] Stop Celery workers
- [ ] Run migrations
- [ ] Verify table creation
- [ ] Test model access
- [ ] Restart application servers
- [ ] Restart Celery workers
- [ ] Monitor error logs
- [ ] Test critical workflows
- [ ] Keep backup for 7 days

---

## Support

If you encounter migration issues:

1. Check Django migration documentation
2. Review error logs in `logs/` directory
3. Verify model imports are correct
4. Check database user permissions
5. Test on fresh database if possible

For rollback assistance, contact your database administrator.
