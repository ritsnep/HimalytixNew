# docs/ALLOCATION_SERVICE_GUIDE.md
# Omnichannel Allocation Service Guide

## Overview

The Allocation Service provides intelligent inventory allocation across multiple warehouses with ATP (Available-to-Promise) calculations, safety stock management, and channel-based prioritization for distributors and multi-warehouse retailers.

## Key Features

- ✅ **Real-time ATP Calculations** - Accurate availability across all warehouses
- ✅ **Multi-Warehouse Allocation** - Optimal allocation strategies
- ✅ **Safety Stock Management** - Prevent stockouts with buffer inventory
- ✅ **Channel Prioritization** - B2B, B2C, retail, wholesale priorities
- ✅ **Future ATP Projections** - Visibility into incoming inventory
- ✅ **Cost Optimization** - Ship from nearest/cheapest warehouse
- ✅ **Backorder Management** - Automatic backorder creation

## Core Concepts

### Available-to-Promise (ATP)

ATP represents inventory that can be promised to customers:

```
ATP = On Hand - Allocated - Safety Stock + In Transit
```

Where:
- **On Hand**: Physical inventory in warehouse
- **Allocated**: Reserved for existing orders (pick lists)
- **Safety Stock**: Buffer to prevent stockouts
- **In Transit**: Inventory being transferred to warehouse

### Allocation Strategies

1. **NEAREST** - Ship from closest warehouse to customer
2. **COST** - Minimize shipping and handling costs
3. **BALANCE** - Balance inventory levels across warehouses
4. **FIFO** - First-In-First-Out (oldest inventory first)
5. **FEFO** - First-Expired-First-Out (for perishables)

### Channel Priorities

1. **CRITICAL** - Critical customers, rush orders (highest priority)
2. **B2B** - Business-to-business customers
3. **RETAIL** - Retail store replenishment
4. **B2C** - Direct to consumer
5. **WHOLESALE** - Wholesale/bulk orders (lowest priority)

## API Endpoints

### Calculate ATP

Get real-time ATP across warehouses:

```http
POST /api/inventory/allocation/atp/
Content-Type: application/json

{
  "product_codes": ["PROD001", "PROD002"],
  "warehouse_code": "WH-001",  // optional
  "include_future": true       // optional, default true
}
```

**Response:**
```json
{
  "PROD001": [
    {
      "warehouse_code": "WH-MAIN",
      "on_hand": 100.0,
      "allocated": 25.0,
      "safety_stock": 10.0,
      "available": 65.0,
      "in_transit": 50.0,
      "future_available": {
        "2025-11-25": 115.0,
        "2025-11-26": 115.0,
        "2025-11-27": 165.0
      }
    },
    {
      "warehouse_code": "WH-WEST",
      "on_hand": 75.0,
      "allocated": 10.0,
      "safety_stock": 5.0,
      "available": 60.0,
      "in_transit": 0.0,
      "future_available": {}
    }
  ]
}
```

### Allocate Inventory

Allocate inventory for an order:

```http
POST /api/inventory/allocation/allocate/
Content-Type: application/json

{
  "product_code": "PROD001",
  "quantity": 50,
  "priority": "B2C",                    // optional
  "customer_id": "CUST001",            // optional
  "preferred_warehouse": "WH-MAIN",    // optional
  "strategy": "nearest"                // optional
}
```

**Strategies:** `nearest`, `cost`, `balance`, `fifo`, `fefo`

**Response:**
```json
{
  "success": true,
  "allocated_quantity": 50.0,
  "backorder_quantity": 0.0,
  "allocations": [
    {
      "warehouse": "WH-MAIN",
      "quantity": 30.0,
      "location": null
    },
    {
      "warehouse": "WH-WEST",
      "quantity": 20.0,
      "location": null
    }
  ],
  "estimated_ship_date": "2025-11-24",
  "message": "Allocated 50.0 from 2 warehouse(s)"
}
```

### Check Order Availability

Check if multi-product order can be fulfilled:

```http
POST /api/inventory/allocation/check-availability/
Content-Type: application/json

{
  "items": [
    {"product_code": "PROD001", "quantity": 10},
    {"product_code": "PROD002", "quantity": 5},
    {"product_code": "PROD003", "quantity": 20}
  ],
  "warehouse_code": "WH-MAIN"  // optional
}
```

**Response:**
```json
{
  "can_fulfill": true,
  "availability": {
    "PROD001": true,
    "PROD002": true,
    "PROD003": false
  },
  "items": [
    {
      "product_code": "PROD001",
      "requested_quantity": 10.0,
      "available": true
    },
    {
      "product_code": "PROD002",
      "requested_quantity": 5.0,
      "available": true
    },
    {
      "product_code": "PROD003",
      "requested_quantity": 20.0,
      "available": false
    }
  ]
}
```

### Get Fulfillment Options

Get warehouse fulfillment options for multi-line order:

```http
POST /api/inventory/allocation/fulfillment-options/
Content-Type: application/json

{
  "items": [
    {"product_code": "PROD001", "quantity": 10},
    {"product_code": "PROD002", "quantity": 5}
  ],
  "priority": "B2B"  // optional
}
```

**Response:**
```json
{
  "options_count": 2,
  "options": [
    {
      "type": "single_warehouse",
      "warehouses": ["WH-MAIN"],
      "split_shipment": false,
      "allocations": [
        {
          "product_code": "PROD001",
          "quantity": 10,
          "available": 65.0
        },
        {
          "product_code": "PROD002",
          "quantity": 5,
          "available": 30.0
        }
      ],
      "priority": 1
    },
    {
      "type": "multi_warehouse",
      "warehouses": ["WH-MAIN", "WH-WEST"],
      "split_shipment": true,
      "allocations_by_warehouse": {
        "WH-MAIN": [
          {"product_code": "PROD001", "quantity": 10, "available": 65.0}
        ],
        "WH-WEST": [
          {"product_code": "PROD002", "quantity": 5, "available": 15.0}
        ]
      },
      "priority": 2
    }
  ]
}
```

## Python Usage Examples

### Basic ATP Calculation

```python
from Inventory.services.allocation_service import AllocationService

# Initialize service
service = AllocationService(organization)

# Calculate ATP for product
atp_results = service.calculate_atp(
    product_code='PROD001',
    warehouse_code=None,  # All warehouses
    include_future=True
)

for atp in atp_results:
    print(f"Warehouse: {atp.warehouse_code}")
    print(f"  On Hand: {atp.on_hand}")
    print(f"  Available: {atp.available}")
    print(f"  In Transit: {atp.in_transit}")
```

### Allocate Inventory with Strategy

```python
from Inventory.services.allocation_service import (
    AllocationService, AllocationRequest,
    AllocationPriority, AllocationStrategy
)
from decimal import Decimal

service = AllocationService(organization)

# Create allocation request
request = AllocationRequest(
    product_code='PROD001',
    quantity=Decimal('50'),
    priority=AllocationPriority.B2C,
    customer_id='CUST001',
    preferred_warehouse='WH-MAIN'
)

# Allocate using NEAREST strategy
result = service.allocate_inventory(
    request,
    strategy=AllocationStrategy.NEAREST
)

if result.success:
    print(f"Allocated {result.allocated_quantity}")
    for allocation in result.allocations:
        print(f"  {allocation['warehouse']}: {allocation['quantity']}")
else:
    print(f"Backorder: {result.backorder_quantity}")
```

### Check Multi-Product Availability

```python
from decimal import Decimal

service = AllocationService(organization)

# Check if order can be fulfilled
product_quantities = {
    'PROD001': Decimal('10'),
    'PROD002': Decimal('5'),
    'PROD003': Decimal('20')
}

availability = service.check_multi_product_availability(
    product_quantities,
    warehouse_code='WH-MAIN'
)

all_available = all(availability.values())
print(f"Can fulfill order: {all_available}")

for product, available in availability.items():
    print(f"  {product}: {'✓' if available else '✗'}")
```

### Get Fulfillment Options

```python
from Inventory.services.allocation_service import AllocationPriority
from decimal import Decimal

service = AllocationService(organization)

product_quantities = {
    'PROD001': Decimal('10'),
    'PROD002': Decimal('5')
}

options = service.get_fulfillment_options(
    product_quantities,
    priority=AllocationPriority.B2B
)

print(f"Found {len(options)} fulfillment option(s)")

for option in options:
    if option['type'] == 'single_warehouse':
        print(f"  Single warehouse: {option['warehouses'][0]}")
    else:
        print(f"  Split across: {', '.join(option['warehouses'])}")
```

## Use Cases

### E-commerce Order Fulfillment

```python
# Customer places order for 3 items
order_items = {
    'WIDGET-A': Decimal('2'),
    'WIDGET-B': Decimal('1'),
    'WIDGET-C': Decimal('3')
}

# 1. Check availability
availability = service.check_multi_product_availability(order_items)

if not all(availability.values()):
    # Some items unavailable - show backorder message
    pass

# 2. Get fulfillment options
options = service.get_fulfillment_options(
    order_items,
    priority=AllocationPriority.B2C
)

# 3. Choose single-warehouse if available (no split shipment)
preferred_option = next(
    (opt for opt in options if not opt['split_shipment']),
    options[0] if options else None
)

# 4. Allocate inventory
for product_code, quantity in order_items.items():
    request = AllocationRequest(
        product_code=product_code,
        quantity=quantity,
        priority=AllocationPriority.B2C,
        customer_id='CUST12345',
        preferred_warehouse=preferred_option['warehouses'][0] if preferred_option else None
    )
    
    result = service.allocate_inventory(request, AllocationStrategy.NEAREST)
    # Create pick list from allocations
```

### B2B Bulk Order

```python
# Wholesale customer orders large quantity
request = AllocationRequest(
    product_code='BULK-ITEM-001',
    quantity=Decimal('1000'),
    priority=AllocationPriority.WHOLESALE,
    customer_id='WHOLESALE-001'
)

# Use BALANCE strategy to spread across warehouses
result = service.allocate_inventory(
    request,
    strategy=AllocationStrategy.BALANCE
)

if result.backorder_quantity > 0:
    # Create backorder for remaining quantity
    create_backorder(
        product='BULK-ITEM-001',
        quantity=result.backorder_quantity,
        customer='WHOLESALE-001'
    )
```

### Retail Store Replenishment

```python
# Store needs replenishment
store_warehouse = 'WH-STORE-01'

# Calculate what's needed
atp_results = service.calculate_atp(
    product_code='RETAIL-ITEM',
    warehouse_code=store_warehouse
)

if atp_results and atp_results[0].available < reorder_point:
    # Allocate from distribution center
    transfer_request = AllocationRequest(
        product_code='RETAIL-ITEM',
        quantity=reorder_quantity,
        priority=AllocationPriority.RETAIL,
        preferred_warehouse='WH-DC-MAIN'
    )
    
    result = service.allocate_inventory(transfer_request)
    # Create inter-warehouse transfer
```

## Safety Stock Calculations

```python
from Inventory.services.allocation_service import SafetyStockService

safety_service = SafetyStockService(organization)

# Calculate optimal safety stock
safety_stock = safety_service.calculate_safety_stock(
    product=product,
    warehouse=warehouse,
    service_level=0.95  # 95% service level
)

# Calculate reorder point
reorder_point = safety_service.get_reorder_point(
    product=product,
    warehouse=warehouse
)

# Calculate Economic Order Quantity
eoq = safety_service.get_economic_order_quantity(
    product=product,
    annual_demand=Decimal('10000'),
    ordering_cost=Decimal('50'),
    holding_cost_percent=Decimal('0.25')  # 25% of item cost
)

print(f"Safety Stock: {safety_stock}")
print(f"Reorder Point: {reorder_point}")
print(f"EOQ: {eoq}")
```

## Performance Considerations

### Caching ATP Results

For high-traffic e-commerce sites, cache ATP calculations:

```python
from django.core.cache import cache

def get_cached_atp(organization, product_code):
    cache_key = f"atp:{organization.id}:{product_code}"
    atp_results = cache.get(cache_key)
    
    if not atp_results:
        service = AllocationService(organization)
        atp_results = service.calculate_atp(product_code)
        cache.set(cache_key, atp_results, timeout=300)  # 5 minutes
    
    return atp_results
```

### Batch ATP Calculations

Calculate ATP for multiple products in one call:

```python
# Get ATP for all products in order
product_codes = ['PROD001', 'PROD002', 'PROD003']
atp_by_product = {}

for code in product_codes:
    atp_by_product[code] = service.calculate_atp(code, include_future=False)
```

## Integration Points

### Order Management System

```python
# When order is created
def allocate_order_inventory(order):
    service = AllocationService(order.organization)
    
    for line in order.lines:
        request = AllocationRequest(
            product_code=line.product.code,
            quantity=line.quantity,
            priority=get_customer_priority(order.customer),
            customer_id=order.customer.id
        )
        
        result = service.allocate_inventory(request)
        
        # Create pick lists from allocations
        for allocation in result.allocations:
            create_pick_list(
                warehouse=allocation['warehouse'],
                product=line.product,
                quantity=allocation['quantity'],
                order_reference=order.order_number
            )
        
        # Handle backorders
        if result.backorder_quantity > 0:
            create_backorder(
                product=line.product,
                quantity=result.backorder_quantity,
                order=order
            )
```

### E-commerce Platform

```python
# Real-time stock check on product page
def get_product_availability(product_code):
    service = AllocationService(current_org)
    atp_results = service.calculate_atp(product_code, include_future=False)
    
    total_available = sum(atp.available for atp in atp_results)
    
    return {
        'in_stock': total_available > 0,
        'quantity_available': total_available,
        'low_stock_warning': total_available < 10,
        'estimated_restock_date': get_next_restock_date(product_code)
    }
```

## Future Enhancements

- [ ] Distance-based warehouse selection (integrate Google Maps API)
- [ ] Predictive ATP using ML demand forecasting
- [ ] Dynamic safety stock based on seasonality
- [ ] Automated inter-warehouse transfers to balance stock
- [ ] Real-time inventory reservations with TTL
- [ ] Multi-channel inventory rules (marketplace allocation)
- [ ] Consignment inventory support
- [ ] Drop-ship allocation logic

---

**Last Updated:** November 24, 2025  
**Version:** 1.0
