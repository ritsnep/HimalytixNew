# Unified Purchasing Flow - System Architecture

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE LAYER                                │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │  unified_form.html                                                 │    │
│  │  ┌──────────────────────────────────────────────────────────────┐ │    │
│  │  │  PURCHASE ORDER / GOODS RECEIPT FORM                         │ │    │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐   │ │    │
│  │  │  │ Header Form  │  │ Line Items   │  │ Real-Time Calc  │   │ │    │
│  │  │  │ - Vendor     │  │ - Product    │  │ - Totals        │   │ │    │
│  │  │  │ - Date       │  │ - Qty        │  │ - Tax           │   │ │    │
│  │  │  │ - Currency   │  │ - Price      │  │ - Variance      │   │ │    │
│  │  │  │ - Notes      │  │ - QC Result  │  │                 │   │ │    │
│  │  │  └──────────────┘  └──────────────┘  └─────────────────┘   │ │    │
│  │  └──────────────────────────────────────────────────────────────┘ │    │
│  │                                                                       │    │
│  │  landed_cost_form.html          purchase_return_form.html            │    │
│  │  ┌─────────────────────────┐   ┌────────────────────────────────┐   │    │
│  │  │ LANDED COST ENTRY       │   │ RETURN CONFIRMATION            │   │    │
│  │  │ - Cost lines            │   │ - Invoice details              │   │    │
│  │  │ - GL accounts           │   │ - Line items to reverse        │   │    │
│  │  │ - Allocation basis      │   │ - GL impact summary            │   │    │
│  │  │ - Auto-calculation      │   │ - Confirmation dialog          │   │    │
│  │  └─────────────────────────┘   └────────────────────────────────┘   │    │
│  └────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          VIEWS LAYER                                        │
│                      (purchasing/unified_views.py)                          │
│                                                                              │
│  PO Workflow              GR Workflow           LC & Return Workflow        │
│  ├─ po_unified_form      ├─ gr_unified_form   ├─ landed_cost_unified_form│
│  ├─ po_detail            ├─ gr_detail         ├─ landed_cost_allocate    │
│  ├─ po_approve           ├─ gr_inspect        ├─ landed_cost_delete      │
│  ├─ po_send              ├─ gr_post           └─ pr_unified_form         │
│  └─ po_cancel            └─ gr_cancel                                    │
│                                                                              │
│  All views:                                                                 │
│  ✓ Require @login_required decorator                                       │
│  ✓ Check organization context                                              │
│  ✓ Validate user permissions                                               │
│  ✓ Use transaction.atomic() for data integrity                             │
│  ✓ Return appropriate error messages                                       │
│  ✓ Support both GET (form) and POST (submit)                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          FORMS LAYER                                        │
│                      (purchasing/forms.py)                                  │
│                                                                              │
│  Base Mixin                Forms                   Formsets                │
│  ├─ OrganizationBoundForm  ├─ PurchaseOrderForm   ├─ PurchaseOrderLineFS  │
│  │  - Filter querysets      ├─ GoodsReceiptForm   ├─ GoodsReceiptLineFS   │
│  │  - Set defaults          ├─ LandedCostDocumentF├─ LandedCostLineFS    │
│  │  - Apply date widgets    │                      │                        │
│  │                          └─ Line Forms          └─ (inline formsets)     │
│  │                             - Quantity              (can_delete=True)    │
│  │                             - Price                                      │
│  │                             - VAT/QC                                     │
│  └──────────────────────────────────────────────────────────────────────    │
│                                                                              │
│  All forms:                                                                 │
│  ✓ Organization-aware field filtering                                      │
│  ✓ Multi-currency support                                                  │
│  ✓ Custom validation methods                                               │
│  ✓ Date widget customization                                               │
│  ✓ Error handling and display                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       SERVICES LAYER                                        │
│                  (purchasing/services/*.py)                                 │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ PurchaseOrderService                GoodsReceiptService            │  │
│  │ ├─ create_purchase_order            ├─ post_goods_receipt         │  │
│  │ ├─ approve_purchase_order           ├─ cancel_goods_receipt       │  │
│  │ ├─ mark_sent                        ├─ _generate_gr_number        │  │
│  │ ├─ cancel_purchase_order            └─ _update_po_status_after_.. │  │
│  │ ├─ close_if_fully_received                                        │  │
│  │ ├─ update_po_line                  ProcurementService            │  │
│  │ ├─ delete_po_line                  ├─ post_purchase_invoice      │  │
│  │ └─ _generate_po_number             ├─ reverse_purchase_invoice   │  │
│  │                                    └─ apply_landed_cost_document │  │
│  │ Matching Service                                                 │  │
│  │ ├─ validate_3way_match                                           │  │
│  │ └─ calculate_variance                                            │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  Service responsibilities:                                                 │
│  ✓ Business logic implementation                                           │
│  ✓ Database transaction management                                         │
│  ✓ GL journal entry creation                                               │
│  ✓ Stock ledger updates                                                    │
│  ✓ Validation and error handling                                           │
│  ✓ Audit trail creation                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MODELS LAYER                                        │
│                      (purchasing/models.py)                                 │
│                                                                              │
│  PurchaseOrder                GoodsReceipt              LandedCost         │
│  ├─ Fields                    ├─ Fields                ├─ Document         │
│  │  - vendor (FK)             │  - purchase_order (FK) │  - purchase_inv...│
│  │  - number (unique)         │  - warehouse (FK)      │  - basis          │
│  │  - order_date              │  - receipt_date        │  - is_applied     │
│  │  - currency (FK)           │  - status              ├─ Lines           │
│  │  - exchange_rate           │  - reference_number    │  - description    │
│  │  - totals                  │  - qc_notes            │  - amount         │
│  │  - status                  ├─ Relations            │  - gl_account (FK)│
│  │  - journal (FK)            │  - lines (1:N)         ├─ Allocations     │
│  ├─ Methods                   ├─ Methods              │  - purchase_line  │
│  │  - recalc_totals()         │  - __str__()           │  - amount         │
│  │  - __str__()               │  - save() / delete()   │  - factor         │
│  │  - save() / delete()       ├─ Status              └─ Methods          │
│  ├─ Status                    │  - DRAFT               │  - __str__()      │
│  │  - DRAFT                   │  - RECEIVED            │  - save()         │
│  │  - APPROVED                │  - INSPECTED                              │
│  │  - SENT                    │  - POSTED                                 │
│  │  - RECEIVED                │  - CANCELLED                              │
│  │  - CLOSED                  │                                            │
│  │                            PurchaseOrderLine                           │
│  ├─ Relations                 ├─ Fields                                   │
│  │  - lines (1:N)             │  - purchase_order (FK)                    │
│  │  - receipts (1:N)          │  - product (FK)                           │
│  └─ Index                     │  - quantity_ordered                       │
│     - (org, number)           │  - quantity_received                      │
│     - (org, status)           │  - quantity_invoiced                      │
│                               │  - unit_price, vat_rate                   │
│                               ├─ Accounts                                 │
│                               │  - inventory_account                      │
│                               │  - expense_account                        │
│                               └─ Property                                 │
│                                  - variance property                      │
│                                  - line_total property                    │
│                                                                              │
│                               GoodsReceiptLine                             │
│                               ├─ Fields                                    │
│                               │  - receipt (FK)                           │
│                               │  - po_line (FK)                           │
│                               │  - quantity_received                      │
│                               │  - quantity_accepted                      │
│                               │  - quantity_rejected                      │
│                               │  - qc_result                              │
│                               │  - batch_number                           │
│                               │  - expiry_date                            │
│                               │  - serial_numbers                         │
│                               └─ Methods                                   │
│                                  - __str__()                              │
│                                  - variance property                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      PERSISTENCE LAYER                                      │
│                    (Django ORM + Database)                                  │
│                                                                              │
│  ┌──────────────┐  ┌──────────────────┐  ┌────────────────────┐           │
│  │ purchase_*   │  │ goods_receipt*   │  │ landed_cost*       │           │
│  │ tables       │  │ tables           │  │ tables             │           │
│  │              │  │                  │  │                    │           │
│  │ ├─ PO        │  │ ├─ GR            │  │ ├─ Document        │           │
│  │ │ ├─ lines   │  │ │ ├─ lines       │  │ │ ├─ lines         │           │
│  │ │ └─ journal │  │ │ ├─ journal     │  │ │ └─ allocations   │           │
│  │ └─ indexes   │  │ │ └─ indexes     │  │ └─ indexes         │           │
│  └──────────────┘  └──────────────────┘  └────────────────────┘           │
│                                                                              │
│  Integration with:                                                          │
│  ├─ accounting.Journal (GL posting)                                        │
│  ├─ accounting.ChartOfAccount (GL accounts)                                │
│  ├─ inventory.StockLedger (stock tracking)                                 │
│  ├─ inventory.Product & Warehouse                                          │
│  └─ usermanagement.Organization (isolation)                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow Diagram

```
                    ┌─── USER INTERACTION ───┐
                    │                         │
                    ▼                         ▼
            ┌───────────────┐        ┌──────────────┐
            │  PO Form      │        │  GR Form     │
            │ (unified_form)│        │ (unified_form)
            └───────────────┘        └──────────────┘
                    │                       │
                    │ POST                  │ POST
                    │                       │
                    ▼                       ▼
            ┌───────────────┐        ┌──────────────┐
            │ po_unified_   │        │ gr_unified_  │
            │ form() view   │        │ form() view  │
            └───────────────┘        └──────────────┘
                    │                       │
                    │ Validate              │ Validate
                    ▼                       ▼
            ┌───────────────┐        ┌──────────────┐
            │ PurchaseOrder │        │ GoodsReceipt │
            │ Form          │        │ Form         │
            └───────────────┘        └──────────────┘
                    │                       │
                    │ form.save()           │ form.save()
                    │ formset.save()        │ formset.save()
                    │                       │
                    ▼                       ▼
            ┌───────────────┐        ┌──────────────┐
            │ PurchaseOrder │        │ GoodsReceipt │
            │ instance      │        │ instance     │
            │ (DRAFT)       │        │ (DRAFT)      │
            └───────────────┘        └──────────────┘
                    │                       │
                    │ po.status=APPROVED    │ gr.status=RECEIVED
                    │ po.save()             │ gr.save()
                    │                       │
                    ▼                       ▼
            ┌───────────────┐        ┌──────────────┐
            │ post_approve()│        │ gr_inspect() │
            │ view          │        │ view         │
            └───────────────┘        └──────────────┘
                    │                       │
                    │                       │ post_goods_receipt()
                    │                       │ (service call)
                    │                       │
                    │                       ▼
                    │              ┌──────────────────┐
                    │              │ GoodsReceipt     │
                    │              │ Service          │
                    │              │ .post_goods_     │
                    │              │  receipt()       │
                    │              └──────────────────┘
                    │                       │
                    │              Create GL Entries
                    │              Update Stock Ledger
                    │              Set status=POSTED
                    │                       │
                    │                       ▼
                    │              ┌──────────────────┐
                    │              │ Accounting       │
                    │              │ Journal (GL)     │
                    │              │                  │
                    │              │ Stock Ledger     │
                    │              └──────────────────┘
                    │                       │
                    │         (Parallel Process)
                    │                       │
                    ▼                       ▼
    ┌────────────────────────────────────────┐
    │                                        │
    │  Invoice Posted                        │
    │  (exists in system)                    │
    │                                        │
    └────────────────────────────────────────┘
                    │
                    │ User navigates to Invoice
                    │ Click "Landed Cost"
                    │
                    ▼
    ┌────────────────────────────────────────┐
    │ landed_cost_unified_form() view        │
    │                                        │
    │ Shows:                                 │
    │ - Invoice summary                      │
    │ - Line items (allocation preview)      │
    │ - Cost entry form                      │
    └────────────────────────────────────────┘
                    │
                    │ POST costs
                    │
                    ▼
    ┌────────────────────────────────────────┐
    │ LandedCostDocument created             │
    │ LandedCostLines created                │
    │                                        │
    │ Status: is_applied = False             │
    └────────────────────────────────────────┘
                    │
                    │ Click "Allocate"
                    │
                    ▼
    ┌────────────────────────────────────────┐
    │ apply_landed_cost_document() service   │
    │                                        │
    │ Calculate allocation factors:          │
    │ - By Value: % of total value           │
    │ - By Quantity: % of total qty          │
    │                                        │
    │ Create LandedCostAllocations           │
    │ Create GL entries for allocations      │
    │ Update invoice line costs              │
    │ Set is_applied = True                  │
    └────────────────────────────────────────┘
                    │
                    ▼
    ┌────────────────────────────────────────┐
    │ Complete Purchasing Cycle              │
    │                                        │
    │ ✓ PO created and sent                  │
    │ ✓ GR received and posted               │
    │ ✓ Invoice costs updated                │
    │ ✓ GL entries recorded                  │
    │ ✓ Stock levels adjusted                │
    └────────────────────────────────────────┘
```

## State Machines

### Purchase Order Status Flow
```
┌─────────┐
│ DRAFT   │◄──── Initial state
└────┬────┘      Can edit all fields
     │
     │ approve()
     ▼
┌─────────────┐
│ APPROVED    │──── Ready for sending
└────┬────────┘    Cannot edit header
     │
     │ send()
     ▼
┌─────────────┐
│ SENT        │──── With vendor
└────┬────────┘    Waiting for receipt
     │
     │ GR posted
     ▼
┌─────────────┐
│ RECEIVED    │──── Goods received
└────┬────────┘    Awaiting closing
     │
     │ close()
     ▼
┌─────────────┐
│ CLOSED      │──── Final state
└─────────────┘    Cannot be changed
     ▲
     │
     │ cancel() (from any state except CLOSED)
     │
     └─────────────────────────
```

### Goods Receipt Status Flow
```
┌─────────┐
│ DRAFT   │◄──── Initial state
└────┬────┘      Edit qty and QC
     │
     │ inspect()
     ▼
┌──────────────┐
│ RECEIVED     │──── Goods received
└────┬─────────┘    QC in progress
     │
     │ update QC
     │
     ▼
┌──────────────┐
│ INSPECTED    │──── QC complete
└────┬─────────┘    Ready for posting
     │
     │ post()
     ▼
┌──────────────┐
│ POSTED       │──── GL & stock updated
└──────────────┘    Final state
     ▲
     │
     │ cancel() (until POSTED)
     │
     └─────────────────────────
    ┌──────────────┐
    │ CANCELLED    │
    └──────────────┘
```

## Permission Matrix

```
Action                          Required Permission
─────────────────────────────────────────────────────
View PO                         purchasing.purchaseorder.view
Create PO                       purchasing.purchaseorder.add
Edit PO (DRAFT only)            purchasing.purchaseorder.change
Approve PO                      purchasing.purchaseorder.change
Send PO                         purchasing.purchaseorder.change
Cancel PO                       purchasing.purchaseorder.change

View GR                         purchasing.goodsreceipt.view
Create GR                       purchasing.goodsreceipt.add
Edit GR (DRAFT only)            purchasing.goodsreceipt.change
Inspect GR                      purchasing.goodsreceipt.change
Post GR                         purchasing.goodsreceipt.change
Cancel GR                       purchasing.goodsreceipt.change

View Invoice                    purchasing.purchaseinvoice.view
Create Landed Cost              purchasing.purchaseinvoice.view
Allocate Landed Cost            purchasing.purchaseinvoice.change
Delete Landed Cost              purchasing.purchaseinvoice.change

Return Invoice                  purchasing.purchaseinvoice.change
```

This architecture provides a scalable, maintainable, and secure purchasing workflow system.
