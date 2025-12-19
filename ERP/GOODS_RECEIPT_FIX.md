# Critical Fix: Goods Receipt Validation Error

## Problem Identified

The Goods Receipt (VM-GR) voucher was experiencing a validation error:
> "Line must have either debit or credit amount, not both or neither"

### Root Cause
1. **Wrong Model Mapping**: Goods Receipt (VM-GR) was being mapped to use `JournalLine` model
2. **Incorrect Validation**: `JournalLine.clean()` validates debit/credit amounts, which don't exist in inventory transactions
3. **Missing Columns**: When validation failed, the form couldn't render properly because the model fields didn't match the UI schema

## Changes Made

### 1. Dynamic Line Section Titles (`generic_voucher_views.py`)
**Problem**: All vouchers showed "Journal Lines" even for non-journal transactions

**Solution**: Added logic to dynamically set line section title based on voucher type:
- **Journal vouchers** (VM08, VM-JV, VM-GJ): "Journal Lines"
- **Inventory vouchers** (codes with INV/STOCK): "Inventory Items"  
- **Receipt vouchers**: "Receipt Items"
- **Invoice vouchers**: "Invoice Items"
- **Purchase/Sales**: "Transaction Items"
- **Default**: "Line Items"

**Files Modified**:
- `accounting/views/generic_voucher_views.py` - Added line_section_title logic in GET and POST methods
- `accounting/templates/accounting/generic_dynamic_voucher_entry.html` - Use `{{ line_section_title|default:"Line Items" }}`

### 2. Model Mapping Fix (`form_factory.py`)
**Problem**: All vouchers defaulting to `JournalLine` regardless of type

**Solution**: Updated `_get_line_model_for_voucher_config()` to:
1. Check voucher code for special cases (GR, RECEIPT → StockAdjustmentLine)
2. Only use JournalLine for actual journal vouchers (VM08, VM-JV, VM-GJ)
3. Map inventory vouchers to `StockAdjustmentLine` as temporary solution

**Code Changed**:
```python
# Special code-based mapping for Goods Receipt
if 'GR' in code or 'RECEIPT' in code:
    return apps.get_model('inventory', 'StockAdjustmentLine')

# Only use JournalLine for actual journal vouchers  
if code in ['VM08', 'VM-JV', 'VM-GJ'] or 'JOURNAL' in code:
    return apps.get_model('accounting', 'JournalLine')
```

## Current Status

### ✅ Fixed
- ✅ Dynamic line section titles (no more "Journal Lines" for inventory)
- ✅ Goods Receipt no longer uses JournalLine (uses StockAdjustmentLine temporarily)
- ✅ Validation error removed for inventory vouchers
- ✅ Error display UX improvements still work

### ⚠️ Temporary Solution
`StockAdjustmentLine` is being used as a **temporary model** for Goods Receipt. This is not ideal because:
- StockAdjustmentLine is for inventory adjustments, not receipts
- It has fields like `counted_quantity` and `system_quantity` which don't make sense for receipts
- Proper goods receipt functionality needs its own model

### ❌ Still Needed - Proper Models

The following voucher types need their own dedicated line models:

#### Inventory Module
1. **GoodsReceiptLine** - for VM-GR (Goods Receipt)
   - Fields: product, quantity, unit_price, total, location, batch, etc.
   
2. **DeliveryNoteLine** - for VM-SD (Sales Delivery)
   - Fields: product, quantity, unit_price, etc.

#### Sales Module  
3. **SalesQuotationLine** - for VM-SQ (Sales Quotation)
4. **SalesReturnLine** - for VM-SR (Sales Return)

#### Purchase Module
5. **PurchaseOrderLine** (already exists, verify it's used)
6. **PurchaseReturnLine** - for VM-PR (Purchase Return)

#### Credit/Debit Notes
7. **CreditNoteLine** - for VM-SCN, VM-PCN
8. **DebitNoteLine** - for VM-SDN, VM-PDN

#### Other
9. **LetterOfCreditLine** - for VM-LC

## Recommended Next Steps

### Immediate (Must Do)
1. **Create GoodsReceiptLine Model**
```python
class GoodsReceiptLine(models.Model):
    receipt = models.ForeignKey('GoodsReceipt', on_delete=models.CASCADE, related_name='lines')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=15, decimal_places=4)
    unit_price = models.DecimalField(max_digits=19, decimal_places=4)
    total_amount = models.DecimalField(max_digits=19, decimal_places=4)
    location = models.ForeignKey(Location, null=True, blank=True, on_delete=models.PROTECT)
    batch = models.ForeignKey(Batch, null=True, blank=True, on_delete=models.PROTECT)
    notes = models.TextField(blank=True)
```

2. **Update form_factory.py** to use proper model:
```python
if 'GR' in code or 'RECEIPT' in code:
    return apps.get_model('inventory', 'GoodsReceiptLine')
```

### Medium Term
1. Create all missing line models for each voucher type
2. Update form_factory.py mappings for each voucher
3. Create migrations for new models
4. Test all voucher types with proper models

### Long Term
1. Consider creating a base LineItem abstract model
2. Implement proper validation per voucher type
3. Add business logic (e.g., update stock on receipt)
4. Create unit tests for each voucher type

## Testing Required

### Test Goods Receipt Now (with StockAdjustmentLine)
1. Navigate to Goods Receipt entry
2. Verify title shows "Receipt Items" not "Journal Lines"
3. Add line items
4. Save - should work WITHOUT validation error
5. Check that columns are visible (not hidden)

### Test After Proper Model Created
1. Repeat above tests
2. Verify stock movements are created
3. Verify proper business logic executes
4. Test error handling

## Impact Analysis

### Files Modified
1. `accounting/views/generic_voucher_views.py` - Line section title logic
2. `accounting/templates/accounting/generic_dynamic_voucher_entry.html` - Dynamic title
3. `accounting/forms/form_factory.py` - Model mapping logic

### Files That Will Need Changes (Future)
1. `inventory/models.py` - Add GoodsReceiptLine and other models
2. `inventory/migrations/` - New migrations
3. `accounting/forms/form_factory.py` - Update all mappings
4. Tests for each voucher type

## Conclusion

The immediate issue is **temporarily resolved** by:
- Using StockAdjustmentLine instead of JournalLine for Goods Receipt
- This removes the debit/credit validation error
- Columns should now be visible

However, this is **NOT a permanent solution**. Proper line models must be created for each voucher type to ensure:
- Correct field validation
- Proper business logic execution
- Data integrity
- Maintainability

**Priority**: Create GoodsReceiptLine model ASAP as Goods Receipt is a core inventory function.
