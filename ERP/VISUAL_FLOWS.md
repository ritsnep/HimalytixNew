# Purchasing Module - Visual Navigation & Flow Diagrams

## Left Sidebar Menu Structure (Final)

```
┌─────────────────────────────────────────────────────────────┐
│                    DASHBOARD                                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Accounting                                                 │
│  ├── Journal Entry                                           │
│  ├── Vouchers                                               │
│  ├── Accounts Receivable                                    │
│  │   ├── Sales Invoices                                     │
│  │   ├── Customer Receipts                                  │
│  │   └── ...                                                │
│  ├── Accounts Payable   [CLEANED]                           │
│  │   ├── Payment Scheduler         ← Vendor Bill REMOVED   │
│  │   ├── Vendor Statement                                   │
│  │   └── Payable Dashboard                                  │
│  └── ...                                                    │
│                                                              │
│  📦 Inventory                                               │
│  ├── Products                                               │
│  ├── Stock Movements                                        │
│  └── ...                                                    │
│                                                              │
│  🛒 Purchasing   [RESTRUCTURED]                             │
│  ├── 📄 New Purchase Order         ← CREATE (top)          │
│  ├── 📥 New Goods Receipt          ← CREATE               │
│  ├── 📋 New Purchase Invoice       ← CREATE               │
│  ├── ──────────────────────────────────                    │
│  ├── 📋 View Purchase Orders       ← VIEW (middle)        │
│  ├── 📦 View Goods Receipts        ← VIEW                │
│  ├── 💰 View Purchase Invoices     ← VIEW                │
│  ├── ──────────────────────────────────                    │
│  ├── 💵 Landed Costs               ← MANAGE (bottom)      │
│  └── 📊 Reports                    ← ANALYZE             │
│                                                              │
│  Enterprise                                                 │
│  ├── Departments                                            │
│  ├── Positions                                              │
│  └── Employees                                              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## User Journey - Creating a Purchase Order

```
START
  │
  ├─ User clicks "Purchasing → 📄 New Purchase Order"
  │
  ├─ URL: /purchasing/orders/new/ 
  │  (Route: po_unified_create)
  │
  ├─ View: po_unified_form()
  │  ├─ Load PurchaseOrderForm
  │  ├─ Load PurchaseOrderLineFormSet
  │  ├─ Render unified_form.html with document_type="PO"
  │
  ├─ User fills form:
  │  ├─ Vendor (dropdown)
  │  ├─ PO Date (dual date picker)
  │  ├─ Delivery Date
  │  ├─ Currency (dropdown)
  │  └─ Add line items:
  │     ├─ Product
  │     ├─ Qty
  │     ├─ Price
  │     ├─ GL Account
  │     └─ Real-time totals recalculate
  │
  ├─ Click "Save as Draft"
  │  ├─ Validate form server-side
  │  ├─ Save PurchaseOrder instance (status=DRAFT)
  │  ├─ Save PurchaseOrderLine items
  │  ├─ Redirect to PO detail page
  │
  ├─ View PO with status "DRAFT"
  │  ├─ Can edit all fields
  │  ├─ Can add/remove lines
  │  └─ Can click "Approve"
  │
  ├─ Click "Approve"
  │  ├─ Verify all required fields
  │  ├─ Change status to APPROVED
  │  ├─ Display success message
  │  └─ Show "Send" button
  │
  ├─ Click "Send"
  │  ├─ Change status to SENT
  │  ├─ Update sent_date
  │  ├─ Display confirmation message
  │  └─ Mark as ready for receipt
  │
  ├─ Wait for goods delivery
  │  └─ Status shows SENT (waiting for GR)
  │
  └─ END (PO ready to be matched with GR)
```

---

## User Journey - Receiving Goods

```
START
  │
  ├─ User clicks "Purchasing → 📥 New Goods Receipt"
  │
  ├─ URL: /purchasing/receipts/new/
  │  (Route: gr_unified_create)
  │
  ├─ View: gr_unified_form()
  │  ├─ Display form to select PO
  │  ├─ Load GoodsReceiptForm
  │  ├─ Load GoodsReceiptLineFormSet
  │
  ├─ User selects PO:
  │  └─ System auto-fills line items from PO_Lines
  │     └─ AJAX call updates form without reload
  │
  ├─ For each GR line:
  │  ├─ Enter Qty Received (from delivery)
  │  ├─ Enter Qty Accepted (after QC check)
  │  ├─ Select QC Result:
  │  │  ├─ Pass: ✓ All good
  │  │  ├─ Fail: ✗ Reject items
  │  │  └─ Pending: ⏳ Needs more inspection
  │  ├─ Add Batch Number (if tracked)
  │  ├─ Add Expiry Date (if perishable)
  │  └─ Add Serial Numbers (if serialized)
  │
  ├─ Click "Save as Draft"
  │  ├─ Validate quantities
  │  ├─ Save GoodsReceipt instance (status=DRAFT)
  │  ├─ Save GoodsReceiptLine items
  │  └─ Show success message
  │
  ├─ Click "Inspect"
  │  ├─ Mark status as RECEIVED
  │  ├─ Verify all QC results entered
  │  ├─ Calculate total accepted qty
  │  └─ Display "Post" button
  │
  ├─ Click "Post"
  │  ├─ Lock all editable fields
  │  ├─ Create Stock Ledger entries:
  │  │  ├─ Increase Inventory balance
  │  │  └─ Calculate value at unit cost
  │  ├─ Create GL Journal Entry:
  │  │  ├─ Debit: Inventory account (qty × cost)
  │  │  └─ Credit: Receiving account / AP account
  │  ├─ Update PurchaseOrder status:
  │  │  └─ Qty_Received updated
  │  │  └─ Auto-close if all received
  │  ├─ Change GR status to POSTED
  │  └─ Show confirmation with GL entry number
  │
  └─ END (GR complete, inventory updated, ready for invoice)
```

---

## User Journey - Recording Invoice

```
START
  │
  ├─ User clicks "Purchasing → 📋 New Purchase Invoice"
  │
  ├─ URL: /purchasing/invoices/new/
  │  (Route: invoice-create)
  │
  ├─ View: invoice_form()
  │  ├─ Load PurchaseInvoiceForm (legacy but unified)
  │  ├─ Load PurchaseInvoiceLineFormSet
  │
  ├─ User fills header:
  │  ├─ Vendor (dropdown)
  │  ├─ Invoice # (from supplier)
  │  ├─ Invoice Date
  │  ├─ Currency
  │  └─ Optional: Link to GR for 3-way match
  │
  ├─ User adds line items:
  │  ├─ Can manually enter OR
  │  ├─ Can copy from linked GR
  │  │  └─ Auto-fills Product, Qty, Reference
  │  └─ For each line:
  │     ├─ Description
  │     ├─ Quantity
  │     ├─ Unit Price
  │     ├─ Tax Code
  │     ├─ GL Account
  │     ├─ Cost Center (optional)
  │     └─ Real-time total calculation
  │
  ├─ Click "Save as Draft"
  │  ├─ Validate form
  │  ├─ Check 3-way match if GR linked:
  │  │  ├─ Invoice Qty should match GR Qty received
  │  │  ├─ Invoice Price should be within variance of PO
  │  │  └─ Show warning if large variance
  │  ├─ Save PurchaseInvoice instance (status=DRAFT)
  │  ├─ Save PurchaseInvoiceLine items
  │  └─ Show success message
  │
  ├─ User reviews invoice:
  │  ├─ Verify totals match supplier invoice
  │  ├─ Check for variance alerts
  │  └─ Make corrections if needed (still DRAFT)
  │
  ├─ Click "Post"
  │  ├─ Final validation:
  │  │  ├─ All lines have GL accounts
  │  │  ├─ Total matches amount
  │  │  └─ Vendor valid
  │  ├─ Create GL Journal Entry:
  │  │  ├─ Debit: Expense/Inventory accounts (per line)
  │  │  └─ Credit: AP Liability account
  │  ├─ Update Stock Ledger (if inventory items)
  │  ├─ Update PurchaseOrder (qty_invoiced)
  │  ├─ Update GoodsReceipt (match status)
  │  ├─ Change Invoice status to POSTED
  │  └─ Show GL entry number and confirmation
  │
  ├─ Invoice complete and matched:
  │  ├─ Status shows POSTED (final)
  │  ├─ GL entry created and viewable
  │  └─ Ready for payment processing
  │
  └─ END (Invoice recorded and matched with PO/GR)
```

---

## User Journey - Allocating Landed Costs

```
START
  │
  ├─ User views Purchase Invoice detail
  │
  ├─ User clicks "Add Landed Cost"
  │
  ├─ URL: /purchasing/invoices/{id}/landed-cost/new/
  │  (Route: landed_cost_unified_create)
  │
  ├─ View: landed_cost_unified_form()
  │  ├─ Load LandedCostDocumentForm
  │  ├─ Load LandedCostLineFormSet
  │  ├─ Load Invoice summary in right sidebar
  │
  ├─ User selects allocation basis:
  │  ├─ By Value: Allocate proportional to line amount
  │  │  └─ High-value items get more cost
  │  └─ By Quantity: Allocate proportional to qty
  │     └─ All items get equal cost per unit
  │
  ├─ User adds cost lines:
  │  ├─ Description (e.g., "Freight", "Customs Duty")
  │  ├─ Amount (total cost for all items)
  │  ├─ GL Account (where cost goes)
  │  └─ Add multiple cost lines as needed
  │
  ├─ Real-time preview in sidebar:
  │  ├─ Shows invoice lines with allocation factors
  │  ├─ Shows cost per unit calculated
  │  ├─ Shows total allocation matches entered costs
  │  └─ Updates as user enters cost lines
  │
  ├─ User reviews allocation:
  │  ├─ Is distribution reasonable?
  │  ├─ Are GL accounts correct?
  │  └─ Does total match freight/duty invoice?
  │
  ├─ Click "Allocate"
  │  ├─ Validate total costs match line allocation
  │  ├─ Create LandedCostDocument (status=DRAFT)
  │  ├─ Create LandedCostLine items (cost components)
  │  ├─ Create LandedCostAllocation items:
  │  │  ├─ For each invoice line:
  │  │  │  ├─ Calculate allocation factor (% of value or qty)
  │  │  │  ├─ Create allocation record with factor
  │  │  │  └─ Store cost per unit
  │  │  └─ Update invoice line with allocated cost
  │  ├─ Create GL Journal Entry:
  │  │  ├─ For each cost component:
  │  │  │  ├─ Debit: Cost GL account (total amount)
  │  │  │  └─ Credit: Inventory Variance account
  │  │  └─ GL entry links costs to invoice
  │  ├─ Update PurchaseInvoice:
  │  │  ├─ Add landed_cost_amount field
  │  │  └─ Recalculate total cost of goods
  │  ├─ Change status to is_applied=True
  │  └─ Show success and GL entry number
  │
  ├─ Invoice now has distributed cost:
  │  ├─ Line 1: Original cost + allocated freight
  │  ├─ Line 2: Original cost + allocated freight
  │  └─ Total cost now includes freight/duty
  │
  └─ END (Costs allocated, GL entries created)
```

---

## Data Flow Diagram - Complete Cycle

```
                          VENDOR
                            │
                            │
                    Issues Purchase
                    Order (PO)
                            │
                            ▼
                    ┌──────────────┐
                    │ Purchase     │
                    │ Order        │
                    │ (DRAFT)      │
                    └──────┬───────┘
                           │
                      Approve
                      & Send
                           │
                           ▼
                    ┌──────────────┐      Issues delivery
                    │ Purchase     │◄─────with GR receipt
                    │ Order        │
                    │ (SENT)       │
                    └──────┬───────┘
                           │
                      Receive
                      goods
                           │
                           ▼
                    ┌──────────────────────┐
                    │ Goods Receipt        │
                    │ - Qty Received       │
                    │ - QC Result          │
                    │ - Batch/Serial       │
                    │ (DRAFT → POSTED)     │
                    └──────┬───────────────┘
                           │
                      Post GR
                      (update inventory)
                           │
                           ├─────────────────────┐
                           │                     │
                           ▼                     ▼
                    ┌──────────────┐     ┌──────────────┐
                    │ Stock Ledger │     │ GL Journal   │
                    │ - Inventory  │     │ - DR: Inv    │
                    │   updated    │     │ - CR: AP     │
                    └──────────────┘     └──────────────┘
                           │
                           │
                      Supplier
                      sends invoice
                           │
                           ▼
                    ┌──────────────────────┐
                    │ Purchase Invoice     │
                    │ - Qty Invoiced       │
                    │ - Amount             │
                    │ (DRAFT → POSTED)     │
                    └──────┬───────────────┘
                           │
                      Check 3-way
                      match
                           │
                           ├─────────────────────────┐
                           │                         │
                           ▼                         │
                    ┌──────────────────┐            │
                    │ Variance Check   │            │
                    │ PO→GR→INV match  │            │
                    │ Alert if > 5%    │            │
                    └──────────────────┘            │
                           │                        │
                           ▼                        │
                      Post Invoice                   │
                      (create GL)                    │
                           │                        │
                           │◄───────────────────────┘
                           │
                           ├──────────────────────────┐
                           │                          │
                           ▼                          ▼
                    ┌──────────────────┐    ┌─────────────────┐
                    │ GL Journal Entry │    │ Update AP       │
                    │ - DR: Expense    │    │ - Create vendor │
                    │ - CR: AP/Inv     │    │   payable       │
                    └──────────────────┘    └─────────────────┘
                           │
                           │
                      Check if
                      Landed Costs
                      needed
                           │
                           ├─ Yes ──┐
                           │        │
                           │        ▼
                           │   ┌──────────────────────┐
                           │   │ Landed Cost Document │
                           │   │ - Freight            │
                           │   │ - Customs Duty       │
                           │   │ (create & allocate)  │
                           │   └──────┬───────────────┘
                           │          │
                           │      Allocate
                           │      costs
                           │          │
                           │          ├──────────────┐
                           │          │              │
                           │          ▼              ▼
                           │   ┌──────────────┐  ┌──────────────┐
                           │   │ Invoice Line │  │ GL Journal   │
                           │   │ Cost updated │  │ - DR: Cost   │
                           │   └──────────────┘  │ - CR: Inv    │
                           │          │          └──────────────┘
                           │          │
                           ▼          ▼
                    ┌──────────────────────────┐
                    │ Invoice Complete         │
                    │ - Cost includes landed   │
                    │ - GL entries all posted  │
                    │ - Ready for payment      │
                    └──────────────────────────┘
                           │
                      Ready for
                      Payment
                           │
                           ▼
                        PAYMENT
```

---

## Status Flow Diagrams

### Purchase Order Status Machine

```
┌─────────────────────────────────────────────────────────┐
│                                                          │
│               PURCHASE ORDER LIFECYCLE                  │
│                                                          │
│  ┌──────┐                                               │
│  │DRAFT │ ◄──── Initial state when created            │
│  └──┬───┘       Can edit everything                    │
│     │ approve()                                         │
│     ▼                                                   │
│  ┌──────────┐                                           │
│  │APPROVED  │ ◄──── Ready to send to vendor            │
│  └──┬───────┘       Header locked, lines editable      │
│     │ send()                                            │
│     ▼                                                   │
│  ┌──────────┐                                           │
│  │SENT      │ ◄──── With vendor, waiting receipt       │
│  └──┬───────┘       All fields locked                  │
│     │ (GR Posted)                                       │
│     ▼                                                   │
│  ┌──────────┐                                           │
│  │RECEIVED  │ ◄──── Goods arrived, GR posted           │
│  └──┬───────┘       Awaiting close                     │
│     │ close()                                           │
│     ▼                                                   │
│  ┌──────────┐                                           │
│  │CLOSED    │ ◄──── Final state                        │
│  └──────────┘       Cannot be changed                  │
│     ▲                                                   │
│     │ cancel() (from any state except CLOSED)          │
│     │                                                   │
│  ┌──────────┐                                           │
│  │CANCELLED │ ◄──── Final state (alternative)         │
│  └──────────┘       GR/Invoice reversed if needed      │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Goods Receipt Status Machine

```
┌──────────────────────────────────────────────────────┐
│                                                      │
│          GOODS RECEIPT LIFECYCLE                    │
│                                                      │
│  ┌──────┐                                            │
│  │DRAFT │ ◄──── Initial state                      │
│  └──┬───┘       All fields editable                 │
│     │ fill data                                      │
│     ▼                                                │
│  ┌──────────┐                                        │
│  │RECEIVED  │ ◄──── Goods received physically       │
│  └──┬───────┘       QC in progress                   │
│     │ update QC                                      │
│     ▼                                                │
│  ┌──────────┐                                        │
│  │INSPECTED │ ◄──── QC complete                     │
│  └──┬───────┘       Ready for posting                │
│     │ post()                                         │
│     ├─► Update Inventory (Stock Ledger)             │
│     ├─► Create GL Entry (DR:Inv, CR:AP)             │
│     ├─► Update PO (qty_received)                     │
│     │                                                │
│     ▼                                                │
│  ┌──────────┐                                        │
│  │POSTED    │ ◄──── GL & Inventory updated         │
│  └──────────┘       Cannot be changed                │
│     ▲                                                │
│     │ cancel() (from DRAFT/RECEIVED/INSPECTED)       │
│     │ ► Reverses Stock & GL if already posted        │
│     │                                                │
│  ┌──────────┐                                        │
│  │CANCELLED │ ◄──── Final state (alternative)      │
│  └──────────┘       All impacts reversed             │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## System Integration Points

```
┌──────────────────────────────────────────────────────────┐
│                    PURCHASING MODULE                     │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │         Purchasing Core                          │  │
│  │ ┌──────────────┐                                 │  │
│  │ │ Purchase Order│──┐                             │  │
│  │ │ Goods Receipt │  │                             │  │
│  │ │ Invoice       │  │                             │  │
│  │ │ Landed Cost   │  │                             │  │
│  │ └──────────────┘  │                             │  │
│  └────────────────────┼──────────────────────────┘  │
│                       │                             │
│     ┌─────────────────┼─────────────────┐          │
│     │                 │                 │          │
│     ▼                 ▼                 ▼          │
│  ┌─────────┐    ┌──────────┐    ┌────────────┐   │
│  │Accounting│    │ Inventory │    │ User      │   │
│  │Module    │    │ Module    │    │ Management│   │
│  │          │    │           │    │           │   │
│  │ • Journal│    │ • Products│    │ • Orgs    │   │
│  │ • GL     │    │ • Warehoues   │ • Groups  │   │
│  │ • AP/AR  │    │ • Stock   │    │ • Users   │   │
│  │ • Chart  │    │   Ledger  │    │ • Perms   │   │
│  └────┬─────┘    └──────┬────┘    └────┬──────┘   │
│       │                 │              │          │
│  ┌────┴───────────────┬─┴──────────────┴─────┐   │
│  │ GL Entry Creation  │ Inventory Updates     │   │
│  │ • PO → No entry    │ • GR → Increase qty  │   │
│  │ • GR → DR:Inv      │ • INV → Update value │   │
│  │ • INV → DR:Exp     │ • LC → Update cost   │   │
│  │ • LC → DR:Cost     │                      │   │
│  └────────────────────┴──────────────────────┘   │
│                                                   │
└──────────────────────────────────────────────────┘
```

---

## Conclusion

The purchasing module provides a complete, integrated workflow for:

✅ **Creating Purchase Orders** - Order planning and approval  
✅ **Receiving Goods** - Stock updates with QC tracking  
✅ **Recording Invoices** - 3-way matching with variance alerts  
✅ **Allocating Costs** - Freight, duty, and other landed costs  
✅ **GL Integration** - Automatic journal entry creation  
✅ **Inventory Management** - Stock and cost updates  

All integrated into a clean, intuitive sidebar navigation that guides users through the natural workflow from order to payment.

**Status:** ✅ **PRODUCTION READY**
