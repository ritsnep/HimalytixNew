# QUICK START GUIDE - Vertical ERP Features

## Table of Contents
1. [Pricing & Promotions](#pricing--promotions)
2. [Fulfillment Workflow](#fulfillment-workflow)
3. [Manufacturing Enhancements](#manufacturing-enhancements)
4. [Subscription Billing](#subscription-billing)
5. [Device & Service Management](#device--service-management)
6. [Automation Tasks](#automation-tasks)

---

## Pricing & Promotions

### Create a Price List
```python
from Inventory.models import PriceList, PriceListItem, Product

# Create price list
price_list = PriceList.objects.create(
    organization=org,
    code='WHOLESALE-2025',
    name='Wholesale Pricing 2025',
    currency_code='USD',
    is_active=True,
    valid_from='2025-01-01',
    valid_to='2025-12-31'
)

# Add products with quantity breaks
product = Product.objects.get(code='PROD-001')

PriceListItem.objects.create(
    price_list=price_list,
    product=product,
    unit_price=100.00,
    min_quantity=1,
    max_quantity=9
)

PriceListItem.objects.create(
    price_list=price_list,
    product=product,
    unit_price=90.00,
    min_quantity=10,
    max_quantity=99
)

PriceListItem.objects.create(
    price_list=price_list,
    product=product,
    unit_price=80.00,
    min_quantity=100
)
```

### Assign Price List to Customer
```python
from Inventory.models import CustomerPriceList

CustomerPriceList.objects.create(
    organization=org,
    customer_id=12345,
    price_list=price_list,
    priority=1,  # Lower = higher priority
    is_active=True
)
```

### Create Promotional Campaign
```python
from Inventory.models import PromotionRule
from django.utils import timezone

promo = PromotionRule.objects.create(
    organization=org,
    code='SUMMER2025',
    name='Summer Sale 2025',
    promo_type='percentage',
    discount_value=20.00,  # 20% off
    valid_from=timezone.now(),
    valid_to='2025-08-31',
    is_active=True,
    max_uses=1000
)

# Add applicable products
promo.apply_to_products.add(product)
```

---

## Fulfillment Workflow

### Pick → Pack → Ship Workflow
```python
from Inventory.services.fulfillment_service import PickPackShipService
from Inventory.models import Warehouse, Product

service = PickPackShipService(organization=org)
warehouse = Warehouse.objects.get(code='WH-01')

# 1. Create pick list
line_items = [
    {'product_id': 101, 'quantity': 10, 'location_id': 1, 'batch_id': None},
    {'product_id': 102, 'quantity': 5, 'location_id': 2, 'batch_id': 5},
]

pick_list = service.create_pick_list(
    warehouse=warehouse,
    order_reference='SO-2025-001',
    line_items=line_items,
    priority=1,
    assigned_to=user_id
)

# 2. Release to warehouse floor
service.release_pick_list(pick_list)

# 3. Record picks
service.record_pick(
    pick_list=pick_list,
    line_number=1,
    quantity_picked=10,
    picked_by=user_id
)

# 4. Create packing slip
packing_slip = service.create_packing_slip(
    pick_list=pick_list,
    num_packages=2,
    total_weight=15.5,
    packed_by=user_id
)

# 5. Complete packing
service.complete_packing(packing_slip)

# 6. Create shipment
shipment = service.create_shipment(
    packing_slip=packing_slip,
    carrier_name='FedEx',
    ship_to_address='123 Main St, City, ST 12345',
    tracking_number='1234567890',
    service_type='Ground',
    shipping_cost=12.50
)

# 7. Update shipment status
service.update_shipment_status(
    shipment=shipment,
    new_status='in_transit'
)
```

### Backorder Management
```python
from Inventory.services.fulfillment_service import BackorderService

service = BackorderService(organization=org)

# Create backorder
backorder = service.create_backorder(
    order_reference='SO-2025-001',
    product=product,
    warehouse=warehouse,
    quantity_backordered=50,
    customer_id=12345,
    expected_date='2025-12-01',
    priority=1
)

# Check availability
available_qty = service.check_backorder_fulfillment_availability(backorder)

# Fulfill when stock arrives
if available_qty > 0:
    backorder, fully_fulfilled = service.fulfill_backorder(
        backorder=backorder,
        quantity_to_fulfill=available_qty
    )
```

### RMA Processing
```python
from Inventory.services.fulfillment_service import RMAService

service = RMAService(organization=org)

# Create RMA
line_items = [
    {'product_id': 101, 'quantity': 2, 'batch_id': 5, 'condition': 'defective'},
]

rma = service.create_rma(
    customer_id=12345,
    original_order='SO-2025-001',
    reason='defective',
    description='Product not working as expected',
    line_items=line_items,
    original_invoice='INV-2025-001',
    warehouse=warehouse
)

# Approve RMA
rma = service.approve_rma(
    rma=rma,
    approved_by=user_id,
    resolution='replace',
    refund_amount=200.00,
    restocking_fee=0.00
)

# Receive goods
rma = service.receive_rma(
    rma=rma,
    warehouse=warehouse,
    location=location
)
```

---

## Manufacturing Enhancements

### Create BOM with Revision
```python
from enterprise.models import BillOfMaterial, BOMRevision, QCCheckpoint

# Create BOM
bom = BillOfMaterial.objects.create(
    organization=org,
    name='Widget Assembly',
    product_name='WDG-001',
    revision='A'
)

# Create revision record
revision = BOMRevision.objects.create(
    organization=org,
    bill_of_material=bom,
    revision_number='A',
    effective_date='2025-01-01',
    is_active=True,
    change_reason='Initial release',
    eco_number='ECO-2025-001'
)
```

### Define QC Checkpoint
```python
qc_checkpoint = QCCheckpoint.objects.create(
    organization=org,
    name='Final Inspection',
    code='QC-FINAL-001',
    checkpoint_type='final',
    test_method='functional',
    specification='Product must pass all functional tests',
    sample_size=1,
    work_center=work_center,
    is_mandatory=True
)
```

### Record Yield Tracking
```python
from enterprise.models import YieldTracking

yield_record = YieldTracking.objects.create(
    organization=org,
    work_order=work_order,
    operation=operation,
    planned_quantity=100,
    actual_quantity=95,
    scrap_quantity=5,
    rework_quantity=2,
    scrap_cost=150.00,
    recorded_by=user_id,
    recorded_date=timezone.now(),
    notes='5 units scrapped due to material defect'
)
# yield_percentage is auto-calculated on save
```

---

## Subscription Billing

### Create Subscription Plan
```python
from billing.models.subscription import SubscriptionPlan, UsageTier

# Create plan
plan = SubscriptionPlan.objects.create(
    organization=org,
    code='BASIC-MONTHLY',
    name='Basic Plan - Monthly',
    plan_type='recurring',
    billing_cycle='monthly',
    base_price=29.99,
    currency_code='USD',
    trial_period_days=14,
    setup_fee=0.00,
    is_active=True
)

# Add usage tiers for hybrid plan
UsageTier.objects.create(
    subscription_plan=plan,
    tier_name='First 1000 API calls',
    min_quantity=0,
    max_quantity=1000,
    price_per_unit=0.00  # Included in base
)

UsageTier.objects.create(
    subscription_plan=plan,
    tier_name='Additional API calls',
    min_quantity=1001,
    price_per_unit=0.01,  # $0.01 per call
    overage_price=0.01
)
```

### Create Subscription
```python
from billing.models.subscription import Subscription

subscription = Subscription.objects.create(
    organization=org,
    subscription_number='SUB-2025-001',
    customer_id=12345,
    subscription_plan=plan,
    status='trial',
    start_date='2025-01-01',
    trial_end_date='2025-01-15',
    current_period_start='2025-01-01',
    current_period_end='2025-01-31',
    next_billing_date='2025-02-01',
    auto_renew=True
)
```

### Record Usage
```python
from billing.models.subscription import SubscriptionUsage

usage = SubscriptionUsage.objects.create(
    subscription=subscription,
    usage_date='2025-01-15',
    usage_type='api_calls',
    quantity=1500,
    unit_of_measure='calls'
)
# calculated_amount will be set by Celery task
```

### Setup Deferred Revenue
```python
from billing.models.subscription import DeferredRevenue, DeferredRevenueSchedule

# Create deferred revenue record
deferred = DeferredRevenue.objects.create(
    organization=org,
    subscription=subscription,
    contract_value=1200.00,  # Annual contract
    deferred_amount=1200.00,
    service_period_start='2025-01-01',
    service_period_end='2025-12-31',
    recognition_method='straight_line',
    deferred_revenue_account=deferred_account,
    revenue_account=revenue_account
)

# Create monthly recognition schedule
for month in range(1, 13):
    DeferredRevenueSchedule.objects.create(
        deferred_revenue=deferred,
        recognition_date=f'2025-{month:02d}-01',
        recognition_amount=100.00  # $1200/12
    )
```

---

## Device & Service Management

### Register Device
```python
from service_management.models import DeviceModel, DeviceLifecycle

# Create device model
device_model = DeviceModel.objects.create(
    organization=org,
    category=category,
    model_number='RTR-5000',
    manufacturer='Cisco',
    model_name='5000 Series Router',
    standard_warranty_months=12,
    cost_price=500.00,
    sale_price=750.00
)

# Register device instance
device = DeviceLifecycle.objects.create(
    organization=org,
    device_model=device_model,
    serial_number='SN123456789',
    asset_tag='AT-001',
    state='inventory',
    warranty_start_date='2025-01-01',
    warranty_end_date='2026-01-01'
)
```

### Deploy Device
```python
device.state = 'provisioning'
device.customer_id = 12345
device.deployment_location = 'HQ - Server Room'
device.save()

# After provisioning
device.state = 'deployed'
device.deployed_date = '2025-01-15'
device.save()
```

### Create Service Contract
```python
from service_management.models import ServiceContract

contract = ServiceContract.objects.create(
    organization=org,
    contract_number='SVC-2025-001',
    customer_id=12345,
    contract_type='premium',
    status='active',
    start_date='2025-01-01',
    end_date='2026-01-01',
    annual_value=5000.00,
    billing_frequency='annual',
    response_time_hours=4,
    resolution_time_hours=24,
    uptime_guarantee_percent=99.95,
    auto_renew=True
)

# Link device to contract
device.service_contract = contract
device.save()
```

### Create Service Ticket
```python
from service_management.models import ServiceTicket

ticket = ServiceTicket.objects.create(
    organization=org,
    ticket_number='TKT-2025-001',
    service_contract=contract,
    device=device,
    customer_id=12345,
    subject='Router not responding',
    description='Router appears to be offline since this morning',
    priority='high',
    status='open',
    assigned_to=support_user_id
)
```

### Process Hardware RMA
```python
from service_management.models import RMAHardware

rma = RMAHardware.objects.create(
    organization=org,
    rma_number='RMA-HW-2025-001',
    device=device,
    service_contract=contract,
    service_ticket=ticket,
    customer_id=12345,
    status='requested',
    failure_type='hardware_failure',
    failure_description='Power supply failed',
    is_under_warranty=device.is_under_warranty
)

# Approve and ship replacement
rma.status = 'approved'
rma.replacement_device = replacement_device
rma.save()
```

---

## Automation Tasks

### Enable Celery Tasks

Add to your `celery_config.py`:
```python
from celery.schedules import crontab

app.conf.beat_schedule = {
    # Inventory tasks
    'check-low-stock-daily': {
        'task': 'Inventory.tasks.check_low_stock_alerts',
        'schedule': crontab(hour=8, minute=0),  # 8 AM daily
    },
    'generate-replenishment-daily': {
        'task': 'Inventory.tasks.generate_replenishment_suggestions',
        'schedule': crontab(hour=9, minute=0),  # 9 AM daily
    },
    'process-backorders': {
        'task': 'Inventory.tasks.process_backorder_fulfillment',
        'schedule': crontab(minute='*/240'),  # Every 4 hours
    },
    'apply-promotions-hourly': {
        'task': 'Inventory.tasks.apply_promotional_pricing',
        'schedule': crontab(minute=0),  # Every hour
    },
    
    # Subscription tasks
    'process-renewals-daily': {
        'task': 'billing.tasks.process_subscription_renewals',
        'schedule': crontab(hour=2, minute=0),  # 2 AM daily
    },
    'recognize-revenue-daily': {
        'task': 'billing.tasks.recognize_deferred_revenue',
        'schedule': crontab(hour=3, minute=0),  # 3 AM daily
    },
    'calculate-usage-daily': {
        'task': 'billing.tasks.calculate_usage_billing',
        'schedule': crontab(hour=4, minute=0),  # 4 AM daily
    },
    'generate-arr-metrics': {
        'task': 'billing.tasks.generate_arr_metrics',
        'schedule': crontab(hour=5, minute=0),  # 5 AM daily
    },
    
    # Service management tasks
    'check-warranty-expiration': {
        'task': 'service_management.tasks.check_device_warranty_expiration',
        'schedule': crontab(hour=7, minute=0),  # 7 AM daily
    },
    'check-sla-breaches': {
        'task': 'service_management.tasks.check_sla_breaches',
        'schedule': crontab(minute='*/60'),  # Every hour
    },
    'process-telemetry': {
        'task': 'service_management.tasks.process_device_telemetry',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
    'auto-renew-contracts': {
        'task': 'service_management.tasks.auto_renew_service_contracts',
        'schedule': crontab(hour=6, minute=0),  # 6 AM daily
    },
    
    # Manufacturing tasks
    'run-mrp-daily': {
        'task': 'enterprise.tasks.run_mrp_calculations',
        'schedule': crontab(hour=6, minute=30),  # 6:30 AM daily
    },
    'process-depreciation-monthly': {
        'task': 'enterprise.tasks.process_depreciation',
        'schedule': crontab(day_of_month=1, hour=1, minute=0),  # 1st of month
    },
}
```

### Run Tasks Manually
```python
# Immediate execution
from Inventory.tasks import check_low_stock_alerts
result = check_low_stock_alerts.delay()

# Get result
print(result.get())
```

---

## Next Steps

1. **Run Migrations:**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

2. **Start Celery Worker:**
   ```bash
   celery -A celery_config worker -l info
   ```

3. **Start Celery Beat (for scheduled tasks):**
   ```bash
   celery -A celery_config beat -l info
   ```

4. **Test Features:**
   - Create price lists and test pricing logic
   - Run through pick-pack-ship workflow
   - Create subscriptions and test billing
   - Register devices and create service tickets

5. **Monitor Tasks:**
   - Use Flower for Celery monitoring
   - Check logs for task execution
   - Review task results in Django admin

---

For detailed API documentation and advanced usage, see the phase 2 implementation guide.
