# Unified Purchasing Flow - Complete Implementation

## Overview

This implementation provides a complete, integrated purchasing workflow for:

1. **Purchase Orders (PO)** - `http://127.0.0.1:8000/purchasing/orders/new/`
2. **Goods Receipts (GR)** - `http://127.0.0.1:8000/purchasing/receipts/new/`
3. **Purchase Returns (PR)** - `http://127.0.0.1:8000/purchasing/invoices/{id}/return/`
4. **Landed Cost Entry** - `http://127.0.0.1:8000/purchasing/invoices/{id}/landed-cost/new/`

All with **editable product/quantity fields**, **real-time calculations**, and **GL integration**.

---

## Routes & URLs

### Purchase Orders
```
GET/POST  /purchasing/orders/new/              - Create new PO (unified form)
GET/POST  /purchasing/orders/<pk>/edit/        - Edit existing PO
GET       /purchasing/orders/<pk>/              - View PO detail
POST      /purchasing/orders/<pk>/approve/      - Approve PO (DRAFT → APPROVED)
POST      /purchasing/orders/<pk>/send/         - Send to vendor (APPROVED → SENT)
POST      /purchasing/orders/<pk>/cancel/       - Cancel PO (→ CLOSED)
```

### Goods Receipts
```
GET/POST  /purchasing/receipts/new/             - Create new GR (unified form)
GET/POST  /purchasing/receipts/<pk>/edit/       - Edit existing GR
GET       /purchasing/receipts/<pk>/             - View GR detail
POST      /purchasing/receipts/<pk>/inspect/    - Mark received (DRAFT → RECEIVED)
POST      /purchasing/receipts/<pk>/post/       - Post to inventory (→ POSTED)
POST      /purchasing/receipts/<pk>/cancel/     - Cancel GR
```

### Purchase Returns
```
GET/POST  /purchasing/invoices/<id>/return/     - Return invoice (creates reversal)
```

### Landed Cost
```
GET/POST  /purchasing/invoices/<id>/landed-cost/new/              - Create landed cost
GET/POST  /purchasing/invoices/<id>/landed-cost/<doc_id>/edit/    - Edit landed cost
POST      /purchasing/landed-cost/<doc_id>/allocate/              - Allocate costs
POST      /purchasing/landed-cost/<doc_id>/delete/                - Delete landed cost
```

---

## Files Created/Modified

### Views
- **`purchasing/unified_views.py`** (NEW) - Complete unified workflow views
  - `po_unified_form()` - PO creation/edit with inline lines
  - `gr_unified_form()` - GR creation/edit with QC tracking
  - `landed_cost_unified_form()` - Landed cost entry with allocation
  - `pr_unified_form()` - Purchase return handler
  - Status action handlers (approve, send, post, cancel, inspect, etc.)

### Forms
- **`purchasing/forms.py`** (UPDATED)
  - `PurchaseOrderForm` & `PurchaseOrderLineForm`
  - `GoodsReceiptForm` & `GoodsReceiptLineForm`
  - `LandedCostDocumentForm` & `LandedCostLineForm`
  - Formsets with organization filtering

### Templates
- **`purchasing/unified_form.html`** (NEW) - Main unified form for PO/GR
- **`purchasing/landed_cost_form.html`** (NEW) - Landed cost entry UI
- **`purchasing/purchase_return_form.html`** (NEW) - Return confirmation
- **`purchasing/po_detail_page.html`** (NEW) - PO detail view
- **`purchasing/gr_detail_page.html`** (NEW) - GR detail view
- **`purchasing/partials/_po_line_row.html`** (NEW) - PO line item row
- **`purchasing/partials/_gr_line_row.html`** (NEW) - GR line item row
- **`purchasing/partials/_landed_cost_line_row.html`** (UPDATED)

### URLs
- **`purchasing/urls.py`** (UPDATED) - New unified routes + legacy compatibility

---

## Features

### 1. Purchase Order Flow
- ✅ Editable product/quantity/pricing
- ✅ Real-time total calculations
- ✅ Multi-currency support
- ✅ VAT/tax tracking per line
- ✅ GL account assignment
- ✅ Status workflow: DRAFT → APPROVED → SENT → RECEIVED → CLOSED
- ✅ Quantity variance tracking (ordered - received - invoiced)

### 2. Goods Receipt Flow
- ✅ Editable received quantities
- ✅ Quality control (pass/fail/pending) tracking
- ✅ Batch/serial number capture
- ✅ Expiry date tracking
- ✅ Multiple receipts per PO support
- ✅ Status workflow: DRAFT → RECEIVED → INSPECTED → POSTED
- ✅ Auto-population from linked PO

### 3. Purchase Return Flow
- ✅ Invoice reversal with GL entries
- ✅ Inventory restoration
- ✅ Status tracking
- ✅ Support for both draft and posted invoices
- ✅ Confirmation UI with impact summary

### 4. Landed Cost Entry
- ✅ Cost component entry (freight, insurance, duty, etc.)
- ✅ GL account assignment per cost line
- ✅ Auto-allocation based on value or quantity
- ✅ Real-time total calculation
- ✅ Allocation preview showing cost distribution
- ✅ Applied cost tracking

---

## Usage Examples

### Creating a Purchase Order
```python
1. Navigate to: http://127.0.0.1:8000/purchasing/orders/new/
2. Select vendor and fill in header details
3. Add line items:
   - Product
   - Quantity ordered
   - Unit cost
   - VAT %
   - GL accounts
4. System auto-calculates totals
5. Click "Save Purchase Order"
6. Status remains DRAFT - can be edited
7. Click "Approve" when ready
8. Click "Send" to vendor
```

### Receiving Goods
```python
1. Navigate to: http://127.0.0.1:8000/purchasing/receipts/new/
2. Select the PO (filters to SENT status)
3. Select warehouse and receipt date
4. System pre-fills PO line items
5. Edit received quantities
6. Add QC results and batch numbers
7. Click "Save Goods Receipt"
8. Click "Mark Received" to change status
9. Click "Post to Inventory" to record GL entries
```

### Recording Landed Costs
```python
1. From Invoice detail: Click "Landed Cost"
2. Enter cost date and basis (by value or quantity)
3. Add cost lines:
   - Description (Freight, Insurance, Customs)
   - Amount
   - GL account (Expense account)
4. System shows total to allocate
5. Click "Save Costs & Allocate"
6. Costs distributed to invoice lines automatically
```

### Returning an Invoice
```python
1. From Invoice detail: Click "Return"
2. Confirmation dialog shows:
   - Original invoice details
   - Line items to reverse
   - GL impact
3. Confirm to execute reversal
4. GL entries created (reversals)
5. Stock quantity restored
6. Invoice moved to DRAFT for correction
```

---

## Models & Data Structures

### PurchaseOrder
```
Status: DRAFT | APPROVED | SENT | RECEIVED | CLOSED
Fields:
  - vendor: FK(Vendor)
  - number: CharField (unique per org)
  - order_date: DateField
  - due_date: DateField (optional)
  - currency: FK(Currency)
  - exchange_rate: DecimalField
  - subtotal, tax_amount, total_amount
  - status: CharField
  - notes: TextField
```

### PurchaseOrderLine
```
Fields:
  - purchase_order: FK(PurchaseOrder)
  - product: FK(Product)
  - quantity_ordered: DecimalField
  - unit_price: DecimalField
  - vat_rate: DecimalField
  - inventory_account: FK(ChartOfAccount)
  - expense_account: FK(ChartOfAccount)
  - quantity_received: DecimalField (tracking)
  - quantity_invoiced: DecimalField (tracking)
Properties:
  - line_total: calculated
  - variance: ordered - (received + invoiced)
```

### GoodsReceipt
```
Status: DRAFT | RECEIVED | INSPECTED | POSTED | CANCELLED
Fields:
  - purchase_order: FK(PurchaseOrder)
  - warehouse: FK(Warehouse)
  - number: CharField
  - receipt_date: DateField
  - reference_number: CharField (AWB/tracking)
  - notes: TextField
  - qc_notes: TextField
  - journal: FK(Journal) (GL link)
  - status: CharField
```

### GoodsReceiptLine
```
Fields:
  - receipt: FK(GoodsReceipt)
  - po_line: FK(PurchaseOrderLine)
  - quantity_received: DecimalField
  - quantity_accepted: DecimalField
  - quantity_rejected: DecimalField
  - qc_result: CharField (pass | fail | pending)
  - batch_number: CharField
  - expiry_date: DateField
  - serial_numbers: TextField
  - notes: TextField
Properties:
  - variance: received - po_line.quantity_ordered
```

### LandedCostDocument
```
Fields:
  - purchase_invoice: OneToOneField(PurchaseInvoice)
  - document_date: DateField
  - basis: CharField (value | quantity)
  - note: CharField
  - is_applied: BooleanField
  - applied_at: DateTimeField
Relations:
  - cost_lines: FK(LandedCostLine)
  - landed_cost_allocations: FK(LandedCostAllocation)
```

### LandedCostLine
```
Fields:
  - document: FK(LandedCostDocument)
  - description: CharField
  - amount: DecimalField
  - gl_account: FK(ChartOfAccount)
```

### LandedCostAllocation
```
Fields:
  - document: FK(LandedCostDocument)
  - purchase_line: FK(PurchaseInvoiceLine)
  - amount: DecimalField
  - factor: DecimalField (% of total)
```

---

## Services & Business Logic

### Services (in `purchasing/services/`)

1. **`post_purchase_order(po, user)`** - Transitions PO through states
2. **`post_goods_receipt(gr, user)`** - Creates GL entries, updates inventory
3. **`apply_landed_cost_document(doc, user)`** - Allocates costs to invoice lines
4. **`reverse_purchase_invoice(invoice, user)`** - Creates GL reversals
5. **`validate_3way_match(po_lines, gr_lines, inv_lines)`** - Matching engine

### Key Validations

- ✅ PO can only be edited in DRAFT status
- ✅ GR can only be created for SENT POs
- ✅ GR quantities must not exceed PO quantities
- ✅ Landed costs can only be applied to POSTED invoices
- ✅ Quantity variance checking (over/under receiving)
- ✅ GL account existence validation
- ✅ Stock availability on reversal

---

## Permissions

All views require organization membership and specific actions:

```
purchasing.purchaseorder.view      - View POs
purchasing.purchaseorder.add       - Create POs
purchasing.purchaseorder.change    - Edit POs
purchasing.goodsreceipt.view       - View GRs
purchasing.goodsreceipt.add        - Create GRs
purchasing.goodsreceipt.change     - Edit GRs
purchasing.purchaseinvoice.view    - View invoices
purchasing.purchaseinvoice.change  - Create/edit invoices
```

---

## Frontend Features

### Dynamic Calculations
- Real-time line total calculations (qty × price)
- Automatic tax calculation per line
- Grand total aggregation
- Quantity variance display

### Inline Editing
- Products can be changed on form
- Quantities editable pre-approval
- Prices editable in DRAFT status
- QC results selectable in GR

### Add/Remove Lines
- "Add line" button for dynamic rows
- Delete checkbox per line
- Form validation on save
- Empty form template for AJAX

### Status Workflows
- Visual status badges
- Context-aware action buttons
- State validation on submission
- Confirmation dialogs for irreversible actions

---

## Testing

### Manual Testing Checklist

1. **Purchase Order**
   - [ ] Create PO with multiple lines
   - [ ] Edit PO before approval
   - [ ] Cannot edit after approval
   - [ ] Approve PO
   - [ ] Send PO
   - [ ] Cancel PO

2. **Goods Receipt**
   - [ ] Create GR from SENT PO
   - [ ] Auto-populate PO lines
   - [ ] Edit received quantities
   - [ ] Add QC results
   - [ ] Mark as received
   - [ ] Post to inventory

3. **Landed Cost**
   - [ ] Add landed costs to invoice
   - [ ] Select allocation basis
   - [ ] View cost distribution
   - [ ] Apply costs

4. **Purchase Return**
   - [ ] Return draft invoice
   - [ ] Return posted invoice
   - [ ] Verify GL reversals
   - [ ] Check stock restoration

### Unit Tests

Located in `purchasing/tests/`:
- `test_purchase_order.py` - PO model and service tests
- `test_goods_receipt.py` - GR model and service tests
- `test_landed_cost.py` - Cost allocation tests
- `test_3way_match.py` - Matching validation tests

Run tests:
```bash
./manage.py test purchasing.tests
pytest purchasing/tests/ -v
```

---

## Known Limitations & Future Enhancements

### Current Limitations
1. GR lines are read-only after receipt (use new GR for corrections)
2. PO-to-GR linking is 1:N (multiple GRs per PO)
3. Landed cost only works with Purchase Invoices (not standalone)
4. No support for partial shipments in single PO

### Future Enhancements
1. **Partial Receipts** - Split PO quantities across multiple GRs
2. **Purchase Returns Model** - Dedicated PR document type
3. **Consignment Tracking** - Support for consignment inventory
4. **Vendor Portal** - Vendors can acknowledge/confirm POs
5. **EDI Integration** - Automated PO transmission via EDI
6. **Analytics Dashboard** - PO-GR-Invoice matching metrics
7. **Auto-GR from ASN** - Advanced Shipment Notice integration
8. **Quality Gates** - QC hold/release workflow before posting

---

## Configuration

### Settings (`settings.py`)

```python
# Purchasing Configuration
PURCHASING = {
    'AUTO_GR_FROM_PO': False,  # Auto-create GR when PO sent
    'REQUIRE_QC_BEFORE_POST': True,  # QC must pass before posting
    '3WAY_MATCH_THRESHOLD': 0.05,  # 5% variance tolerance
    'LANDED_COST_AUTO_ALLOCATE': True,  # Auto-allocate on save
}
```

### Logging

All purchasing operations are logged to:
- `logs/purchasing.log`
- GL Entry Journal (accounting module)
- Stock Ledger (inventory module)

---

## Troubleshooting

### Common Issues

**1. "Cannot create GR for this PO"**
- Reason: PO status is not SENT
- Solution: Approve and send PO first

**2. "GL account not found"**
- Reason: Account doesn't exist in organization
- Solution: Create account in Chart of Accounts

**3. "Stock quantity insufficient for reversal"**
- Reason: Inventory was already consumed
- Solution: Adjust stock manually first

**4. "Landed costs cannot be applied"**
- Reason: Invoice is not POSTED status
- Solution: Post invoice before applying landed costs

---

## Support & Maintenance

For issues or questions:
1. Check this documentation
2. Review unit tests for usage examples
3. Check GL Journal for posting errors
4. Verify organization permissions
5. Review stock ledger for inventory impacts

---

## Summary

This unified purchasing flow provides a complete, production-ready system for:
- **Planning** (PO creation with full detail)
- **Receiving** (GR with QC tracking)
- **Costing** (Landed cost allocation)
- **Settlement** (Invoice matching, 3-way validation)
- **Reversals** (Complete return handling)

All with real-time calculations, GL integration, and comprehensive audit trails.
