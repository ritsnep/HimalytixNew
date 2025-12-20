# Unified Purchasing Flow - Quick Start Guide

## For Developers

### Running the Application

1. **Start the Django server:**
   ```bash
   cd /path/to/Himalytix/ERP
   ./manage.py runserver
   ```

2. **Access the purchasing module:**
   - Base: http://127.0.0.1:8000/purchasing/

### Creating a Purchase Order

**URL:** `http://127.0.0.1:8000/purchasing/orders/new/`

**Form Fields:**
- Vendor (required)
- Order Date (required)
- Currency (required)
- Due Date (optional)
- Exchange Rate (default: 1)
- Notes (optional)

**Line Items:**
- Product (required)
- Qty Ordered (required)
- Unit Cost (required)
- VAT % (default: 0)
- Inventory Account (optional)
- Expense Account (optional)

**Status Flow:**
1. Draft (can edit all fields)
2. Approved (notify vendor)
3. Sent (waiting for goods)
4. Received (GR posted)
5. Closed (final)

### Creating a Goods Receipt

**URL:** `http://127.0.0.1:8000/purchasing/receipts/new/`

**Prerequisites:**
- Must have a Purchase Order in SENT status

**Form Fields:**
- Purchase Order (required, auto-filtered to SENT)
- Warehouse (required)
- Receipt Date (required)
- Reference # (optional, e.g., AWB number)
- QC Notes (optional)

**Line Items (auto-populated from PO):**
- Product (readonly)
- Qty Ordered (readonly)
- Qty Received (editable)
- Qty Accepted (editable)
- QC Result (pass/fail/pending)
- Batch # (optional)
- Expiry Date (optional)

**Status Flow:**
1. Draft (edit quantities/QC)
2. Received (mark as received)
3. Inspected (QC complete)
4. Posted (GL entries created)

### Recording Landed Costs

**URL:** `http://127.0.0.1:8000/purchasing/invoices/{invoice_id}/landed-cost/new/`

**Form Fields:**
- Document Date (required)
- Basis (required: by value or quantity)
- Notes (optional)

**Cost Lines:**
- Description (Freight, Insurance, Customs Duty, etc.)
- Amount (required)
- GL Account (required)

**Process:**
1. Add all cost lines
2. Click "Save Costs & Allocate"
3. System auto-allocates to invoice lines based on basis
4. GL entries created for cost distribution

### Returning an Invoice

**URL:** `http://127.0.0.1:8000/purchasing/invoices/{invoice_id}/return/`

**Process:**
1. Confirmation screen shows all reversals
2. GL impact displayed
3. Click "Confirm Return" to execute
4. Invoice moved to DRAFT, GL entries reversed, stock restored

---

## API Examples

### Create Purchase Order (via Python)

```python
from purchasing.models import PurchaseOrder, PurchaseOrderLine
from accounting.models import Vendor, Currency
from inventory.models import Product, Warehouse
from usermanagement.models import Organization

org = Organization.objects.get(code='TEST')
vendor = Vendor.objects.get(name='Supplier Name')
product = Product.objects.get(sku='PROD-001')
currency = Currency.objects.get(currency_code='USD')
warehouse = Warehouse.objects.get(name='Main')

# Create PO
po = PurchaseOrder.objects.create(
    organization=org,
    vendor=vendor,
    number='PO-2025-001',
    order_date='2025-12-20',
    currency=currency,
    status=PurchaseOrder.Status.DRAFT
)

# Add line
line = PurchaseOrderLine.objects.create(
    purchase_order=po,
    product=product,
    quantity_ordered=100,
    unit_price=10.00,
    vat_rate=10,
    inventory_account=inv_account
)

# Recalculate totals
po.recalc_totals()
po.save()

# Approve
po.status = PurchaseOrder.Status.APPROVED
po.save()

# Send
po.status = PurchaseOrder.Status.SENT
po.save()
```

### Create Goods Receipt

```python
from purchasing.models import GoodsReceipt, GoodsReceiptLine

gr = GoodsReceipt.objects.create(
    organization=org,
    purchase_order=po,
    number='GR-2025-001',
    receipt_date='2025-12-20',
    warehouse=warehouse,
    status=GoodsReceipt.Status.DRAFT
)

# Add line from PO
po_line = po.lines.first()
gr_line = GoodsReceiptLine.objects.create(
    receipt=gr,
    po_line=po_line,
    quantity_received=100,
    quantity_accepted=100,
    qc_result='pass'
)

# Post
gr.status = GoodsReceipt.Status.RECEIVED
gr.save()

gr.status = GoodsReceipt.Status.POSTED
gr.save()
```

### Apply Landed Costs

```python
from purchasing.models import LandedCostDocument, LandedCostLine
from purchasing.services import apply_landed_cost_document

lc_doc = LandedCostDocument.objects.create(
    organization=org,
    purchase_invoice=invoice,
    document_date='2025-12-20',
    basis=LandedCostDocument.LandedCostBasis.BY_VALUE
)

LandedCostLine.objects.create(
    document=lc_doc,
    description='Freight',
    amount=100.00,
    gl_account=expense_account
)

# Apply allocation
apply_landed_cost_document(lc_doc, user=request.user)
```

---

## Testing

### Run all purchasing tests:
```bash
./manage.py test purchasing
```

### Run specific test:
```bash
./manage.py test purchasing.tests.test_unified_flow.TestUnifiedPurchasingFlow.test_complete_purchasing_flow
```

### Run with coverage:
```bash
coverage run --source='purchasing' manage.py test purchasing
coverage report
coverage html
```

---

## Troubleshooting

### Issue: "Cannot create GR for this PO"
**Solution:** PO must be in SENT status. Approve and send PO first.

### Issue: "GL account not found"
**Solution:** Create account in Chart of Accounts first.

### Issue: "Landed cost allocation failed"
**Solution:** Invoice must be in POSTED status before applying landed costs.

### Issue: Form validation errors
**Solution:** Check organization field values - all lookups are org-filtered.

---

## File Structure

```
purchasing/
├── models.py                 # PO, GR, LandedCost models
├── forms.py                 # Forms and formsets
├── unified_views.py         # Main workflow views (NEW)
├── urls.py                  # URL routing
├── services/
│   ├── __init__.py
│   ├── procurement.py       # Invoice, landing cost services
│   ├── purchase_order_service.py
│   ├── goods_receipt_service.py
│   ├── matching_service.py
│   └── ...
├── tests/
│   ├── test_unified_flow.py (NEW)
│   └── ...
└── templates/
    ├── unified_form.html          (NEW)
    ├── landed_cost_form.html      (NEW)
    ├── purchase_return_form.html  (NEW)
    ├── po_detail_page.html        (NEW)
    ├── gr_detail_page.html        (NEW)
    └── partials/
        ├── _po_line_row.html      (NEW)
        ├── _gr_line_row.html      (NEW)
        └── ...
```

---

## Key Classes & Methods

### PurchaseOrder
- `recalc_totals()` - Recalculate subtotal/tax/total
- `Status.choices` - Draft, Approved, Sent, Received, Closed

### GoodsReceipt
- `Status.choices` - Draft, Received, Inspected, Posted, Cancelled
- Linked to PurchaseOrder (1:N relationship)

### PurchaseOrderLine
- `variance` - Property: ordered - (received + invoiced)
- Tracks quantity_ordered, quantity_received, quantity_invoiced

### GoodsReceiptLine
- `qc_result` - pass, fail, or pending
- `batch_number`, `expiry_date` - Traceability fields

### LandedCostDocument
- `basis` - Allocation method: by_value or by_quantity
- `is_applied` - Track if costs have been allocated

---

## Next Steps

1. **Test the flows** - Create PO → GR → Landed Cost
2. **Review GL postings** - Check accounting journal entries
3. **Verify stock** - Confirm inventory updates
4. **Test reversals** - Return invoice and verify GL reversals
5. **Review audit trail** - Check logging and transaction records

---

## Support

For issues or questions:
1. Check the comprehensive documentation in UNIFIED_PURCHASING_FLOW.md
2. Review test cases in test_unified_flow.py
3. Check GL Journal for posting errors
4. Review organization permissions
5. Check logs/ for error details
