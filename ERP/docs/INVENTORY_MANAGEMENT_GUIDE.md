# Inventory Management Implementation Guide

## Overview

This document describes the complete inventory management system with stock tracking and Cost of Goods Sold (COGS) integration.

## Architecture

The inventory system uses:
- **InventoryPostingService**: Handles inventory receipts and issues with weighted-average costing
- **Product Model**: Master data with GL account assignments
- **Warehouse & Location**: Physical storage tracking
- **InventoryItem**: Current stock snapshot (quantity on hand, unit cost)
- **StockLedger**: Immutable transaction history

## 1. Product and Warehouse Setup

### Product Configuration

Each inventory item **must** have:
- `is_inventory_item = True`
- `inventory_account`: Asset account (e.g., "1140 - Inventory")
- `expense_account`: COGS account (e.g., "5000 - Cost of Goods Sold")

**Validation**: The Product model enforces these requirements via `clean()` method:

```python
def clean(self):
    if self.is_inventory_item:
        if not self.inventory_account:
            raise ValidationError('Inventory account is required for inventory items.')
        if not self.expense_account:
            raise ValidationError('COGS (expense) account is required for inventory items.')
```

### Warehouse Setup

Create warehouses in the admin or via `/inventory/warehouses/`:
- Each warehouse has a code and name
- Optionally assign a default inventory_account at warehouse level

## 2. Sales (Issue) Flow

### Process Overview

When posting a sales invoice with inventory items:

1. **User selects warehouse** on the sales invoice form
2. **Service validates** that inventory items have required accounts
3. **InventoryPostingService.record_issue()** is called:
   - Decrements `InventoryItem.quantity_on_hand`
   - Creates `StockLedger` entry with `txn_type='issue'`
   - Returns COGS amount at weighted-average cost
4. **Journal entries created**:
   ```
   Dr. COGS (expense_account)         XXX
       Cr. Inventory (inventory_account)   XXX
   Dr. Accounts Receivable             XXX
       Cr. Revenue                          XXX
   ```

### Code Example

From `sales_invoice_service.py`:

```python
if product and product.is_inventory_item:
    if warehouse is None:
        raise ValidationError("Warehouse is required when posting inventory items.")
    
    issue = inventory_service.record_issue(
        product=product,
        warehouse=warehouse,
        quantity=sil.quantity,
        reference_id=invoice.invoice_number,
        cogs_account=product.expense_account,
    )
    
    # Dr COGS
    JournalLine.objects.create(
        journal=journal,
        account=issue.debit_account,
        description=f"COGS for {product.code}",
        debit_amount=issue.total_cost,
        ...
    )
    # Cr Inventory
    JournalLine.objects.create(
        journal=journal,
        account=issue.credit_account,
        description=f"Inventory out for {product.code}",
        credit_amount=issue.total_cost,
        ...
    )
```

### Testing Sales Flow

1. Create a product with `is_inventory_item=True`
2. Assign inventory and COGS accounts
3. Receive stock via purchase invoice (see below)
4. Create sales invoice with the product
5. Select warehouse before posting
6. Post the invoice
7. Verify:
   - Stock quantity decreased in `/inventory/stock/`
   - StockLedger entry created in `/inventory/ledger/`
   - Journal has COGS and Inventory GL lines

## 3. Purchase (Receipt) Flow

### Process Overview with GR/IR

When posting a purchase invoice with inventory items and GR/IR enabled:

1. **User selects**:
   - Warehouse for receipt
   - GR/IR account (Goods Receipt/Invoice Receipt clearing account)
2. **InventoryPostingService.record_receipt()** is called:
   - Increases `InventoryItem.quantity_on_hand`
   - Updates `InventoryItem.unit_cost` using weighted-average:
     ```
     new_cost = (old_qty * old_cost + new_qty * new_cost) / (old_qty + new_qty)
     ```
   - Creates `StockLedger` entry with `txn_type='receipt'`
3. **Journal entries created** (GR/IR method):
   ```
   # Receipt of goods
   Dr. Inventory (inventory_account)     XXX
       Cr. GR/IR (clearing)                   XXX
   
   # Clearing GR/IR against AP
   Dr. GR/IR (clearing)                   XXX
       Cr. Accounts Payable                   XXX
   ```

### Code Example

From `purchase_invoice_service.py`:

```python
if use_grir and product and product.is_inventory_item:
    receipt = inventory_service.record_receipt(
        product=product,
        warehouse=warehouse,
        quantity=pil.quantity,
        unit_cost=pil.unit_cost,
        grir_account=grir_account,
        reference_id=invoice.invoice_number,
    )
    
    # Dr Inventory
    JournalLine.objects.create(
        journal=journal,
        account=receipt.debit_account,
        description=f"Inventory receipt for {product.code}",
        debit_amount=receipt.total_cost,
        ...
    )
    # Cr GR/IR
    JournalLine.objects.create(
        journal=journal,
        account=receipt.credit_account,
        description=f"GR/IR for {product.code}",
        credit_amount=receipt.total_cost,
        ...
    )
    # Dr GR/IR (clearing)
    JournalLine.objects.create(
        journal=journal,
        account=receipt.credit_account,
        description=f"GR/IR clearing for {product.code}",
        debit_amount=receipt.total_cost,
        ...
    )
```

### Testing Purchase Flow

1. Create GR/IR clearing account (Type: Liability or Asset, typically 2140)
2. Create purchase invoice with inventory items
3. Select warehouse and GR/IR account
4. Post the invoice
5. Verify:
   - Stock quantity increased
   - Unit cost updated to weighted average
   - StockLedger shows receipt
   - Journal has Inventory Dr, GR/IR Cr entries

## 4. Stock Reports

### Current Stock Report (`/inventory/stock/`)

Shows real-time inventory levels:

- **URL**: `/inventory/stock/`
- **Features**:
  - Filter by warehouse, product
  - Shows quantity on hand, unit cost, total value
  - Displays location and batch if tracked
- **Use Cases**:
  - Check available stock
  - View stock value by warehouse
  - Identify low stock items

### Stock Ledger Report (`/inventory/ledger/`)

Shows complete movement history:

- **URL**: `/inventory/ledger/`
- **Features**:
  - Filter by warehouse, product, transaction type
  - Date range filtering
  - Shows qty in/out, unit cost, reference
  - Limited to 100 most recent entries
- **Use Cases**:
  - Audit trail for stock movements
  - Reconcile physical vs system stock
  - Track specific transactions

### Admin Reports

Also available in Django Admin:
- **Stock Summary**: `/admin/inventory/stocksummary/`
- **Stock Ledger Report**: `/admin/inventory/stockledgerreport/`

## 5. Database Changes

### New Fields Added

**SalesInvoice Model**:
```python
warehouse = models.ForeignKey(
    'inventory.Warehouse',
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='sales_invoices',
    help_text='Warehouse for inventory items in this invoice',
)
```

**PurchaseInvoice Model**:
```python
warehouse = models.ForeignKey(
    'inventory.Warehouse',
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='purchase_invoices',
    help_text='Warehouse for receiving inventory items',
)
grir_account = models.ForeignKey(
    'ChartOfAccount',
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='purchase_invoice_grir',
    help_text='Goods Receipt/Invoice Receipt clearing account',
)
```

### Migration Required

Run migrations to apply database changes:
```bash
python manage.py makemigrations
python manage.py migrate
```

## 6. Form Updates

### SalesInvoiceForm

Now includes warehouse field:
- Optional field (required only if selling inventory items)
- Filtered to show only active warehouses for the organization
- Help text: "Required when selling inventory items"

### PurchaseInvoiceForm

Now includes:
- `warehouse`: For receiving inventory
- `grir_account`: GR/IR clearing account
- Both filtered by organization

## 7. End-to-End Testing Checklist

### Setup Phase
- [ ] Create warehouse (e.g., "WH01 - Main Warehouse")
- [ ] Create GL accounts:
  - [ ] Inventory asset (1140)
  - [ ] COGS expense (5000)
  - [ ] GR/IR clearing (2140)
- [ ] Create product:
  - [ ] Set `is_inventory_item=True`
  - [ ] Assign inventory_account
  - [ ] Assign expense_account (COGS)

### Purchase Receipt Test
- [ ] Create purchase invoice with product
- [ ] Select warehouse
- [ ] Select GR/IR account
- [ ] Post invoice
- [ ] Verify stock increased at `/inventory/stock/`
- [ ] Verify ledger entry at `/inventory/ledger/`
- [ ] Verify GL entries in journal

### Sales Issue Test
- [ ] Create sales invoice with product
- [ ] Select warehouse
- [ ] Post invoice
- [ ] Verify stock decreased
- [ ] Verify COGS GL entry created
- [ ] Verify inventory GL entry (credit)

### Reporting Test
- [ ] Access `/inventory/stock/` - see current levels
- [ ] Filter by warehouse - verify filtering works
- [ ] Access `/inventory/ledger/` - see all movements
- [ ] Filter by product and date range

## 8. Error Handling

The system will raise errors if:

- **Missing accounts**: "Product is missing inventory or expense (COGS) account"
- **No warehouse**: "Warehouse is required when posting inventory items"
- **Insufficient stock**: "Insufficient quantity on hand for issue"
- **No GR/IR account**: "GR/IR account must be provided when use_grir is True"

## 9. Best Practices

1. **Always set up GL accounts first** before marking products as inventory items
2. **Use consistent warehouse** for each customer/location
3. **Review stock levels** before month-end closing
4. **Reconcile physical counts** with system quantities regularly
5. **Use batch tracking** for perishable items or lot control
6. **Set reorder levels** on products to get low-stock alerts

## 10. API Endpoints

For integration or programmatic access:

- Stock levels: Query `InventoryItem` model
- Ledger history: Query `StockLedger` model
- Use DRF serializers if REST API is enabled

## Summary

The inventory management system is now fully integrated with:
- ✅ Product master data with GL account validation
- ✅ Warehouse and location tracking
- ✅ Weighted-average costing via InventoryPostingService
- ✅ Sales invoice integration (issues stock, posts COGS)
- ✅ Purchase invoice integration (receives stock, updates cost)
- ✅ Stock and ledger reports with filtering
- ✅ Complete audit trail via StockLedger

All transactions create proper GL entries and maintain referential integrity between inventory and accounting modules.

## Costing Method Selection

Inventory masters can now select how each SKU is valued:

1. Open the product form (`/inventory/products/<id>/edit/` or via the product create page).
2. Scroll to the **Costing Method** block, choose between `Weighted Average`, `FIFO`, `LIFO`, or `Standard Cost`, and save.
3. Provide a **Standard Cost** when the Standard option is active; FIFO and LIFO will build `CostLayer` records per receipt and consume them when issuing stock.
