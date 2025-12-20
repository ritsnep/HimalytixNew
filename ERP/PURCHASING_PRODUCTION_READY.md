# Purchasing Module - Production Ready Setup

## Overview

The purchasing module has been optimized and finalized for production deployment. The module provides a complete, unified workflow for managing purchase orders, goods receipts, purchase invoices, and landed cost allocation.

**Last Updated:** December 20, 2025  
**Status:** ✅ Production Ready  
**Version:** 2.0 (Unified Workflow)

---

## Quick Navigation - Left Sidebar

The left sidebar now provides a clean, organized entry point to all purchasing functions:

```
Purchasing (shopping-bag icon)
├── 📄 New Purchase Order      → Create/submit POs
├── 📥 New Goods Receipt       → Receive stock from PO
├── 📋 New Purchase Invoice    → Record supplier invoice
├── ─────────────────────────────
├── 📋 View Purchase Orders    → List of all POs with status
├── 📦 View Goods Receipts     → List of all GRs with status
├── 💰 View Purchase Invoices  → List of all invoices
├── ─────────────────────────────
├── 💵 Landed Costs            → Manage freight/duty allocation
└── 📊 Reports                 → Purchase analytics
```

### Removed Items (Legacy)

The following legacy items have been removed from navigation:
- **Accounting → Accounts Payable → Vendor Bill Entry** ❌ (moved to Purchasing → New Purchase Invoice)
- **Purchasing → Purchase Orders (table view)** → Use "View Purchase Orders" instead
- **Purchasing → Goods Receipts (table view)** → Use "View Goods Receipts" instead

---

## Core Workflows

### 1. Purchase Order Flow

**URL:** `purchasing:po_unified_create`

**Steps:**
1. Click **Purchasing → New Purchase Order**
2. Fill header: Vendor, PO Date, Currency, Delivery Date
3. Add line items: Product, Qty, Price, GL Account
4. Save as DRAFT
5. Review and click **Approve**
6. Click **Send** to vendor
7. Status transitions: DRAFT → APPROVED → SENT → RECEIVED → CLOSED

**Key Features:**
- Real-time total calculations
- Multi-currency support
- Dual date input (AD/BS)
- GL account assignment per line
- Variance tracking (ordered vs. received)

---

### 2. Goods Receipt Flow

**URL:** `purchasing:gr_unified_create`

**Steps:**
1. Click **Purchasing → New Goods Receipt**
2. Select related Purchase Order
3. System pre-fills line items from PO
4. Enter quantities received, accepted, rejected
5. Add QC notes (pass/fail/pending)
6. Add batch numbers and expiry dates (if applicable)
7. Click **Inspect** to mark QC complete
8. Click **Post** to update inventory and GL
9. Status transitions: DRAFT → RECEIVED → INSPECTED → POSTED

**Key Features:**
- Auto-fill from PO (reduces data entry errors)
- QC tracking per line item
- Batch/Serial number support
- Expiry date tracking
- Stock ledger updates on posting
- GL entries generated automatically

---

### 3. Purchase Invoice Flow

**URL:** `purchasing:invoice-create`

**Steps:**
1. Click **Purchasing → New Purchase Invoice**
2. Fill header: Vendor, Invoice #, Invoice Date
3. Link to GR or enter line items manually
4. Confirm totals and GL distribution
5. Save as DRAFT
6. Click **Post** to finalize and generate GL entries
7. Status transitions: DRAFT → POSTED

**Key Features:**
- 3-way matching: PO → GR → Invoice
- Variance detection
- Automatic GL posting
- Multiple tax support
- Payment term tracking
- Discount handling

---

### 4. Landed Cost Allocation

**URL:** `purchasing:landed_cost_unified_create` (from Invoice detail)

**Steps:**
1. Open Purchase Invoice
2. Click **Add Landed Cost**
3. Select allocation basis: By Value or By Quantity
4. Add cost lines: Description, Amount, GL Account
5. Review allocation breakdown in sidebar
6. Click **Allocate**
7. System distributes costs across invoice lines
8. GL entries created for cost allocation

**Key Features:**
- Flexible allocation basis
- Real-time preview
- GL account assignment per cost component
- Automatic factor calculation
- Complete audit trail

---

### 5. Purchase Return Flow

**URL:** `purchasing:pr_unified_create`

**Steps:**
1. Click **Purchasing → New Purchase Return** (or from Invoice → Return button)
2. Select original invoice to reverse
3. System pre-fills all line items
4. Adjust quantities if partial return
5. Add return reason/notes
6. Preview GL impact in sidebar
7. Click **Confirm Return**
8. System creates reversal GL entries

**Key Features:**
- Invoice reversal with GL impact tracking
- Partial return support
- Complete audit trail
- Inventory adjustment tracking

---

## URL Mapping

### Production Routes (New Unified Flow)

| Purpose | URL Pattern | View Function | Name |
|---------|----------|--------|------|
| Create PO | `/purchasing/orders/new/` | `po_unified_form` | `po_unified_create` |
| Edit PO | `/purchasing/orders/<pk>/edit/` | `po_unified_form` | `po_unified_edit` |
| View PO | `/purchasing/orders/<pk>/` | `po_detail` | `po_detail` |
| Approve PO | `/purchasing/orders/<pk>/approve/` | `po_approve` | `po_unified_approve` |
| Send PO | `/purchasing/orders/<pk>/send/` | `po_send` | `po_unified_send` |
| Cancel PO | `/purchasing/orders/<pk>/cancel/` | `po_cancel` | `po_unified_cancel` |
| | | | |
| Create GR | `/purchasing/receipts/new/` | `gr_unified_form` | `gr_unified_create` |
| Edit GR | `/purchasing/receipts/<pk>/edit/` | `gr_unified_form` | `gr_unified_edit` |
| View GR | `/purchasing/receipts/<pk>/` | `gr_detail` | `gr_detail` |
| Inspect GR | `/purchasing/receipts/<pk>/inspect/` | `gr_inspect` | `gr_unified_inspect` |
| Post GR | `/purchasing/receipts/<pk>/post/` | `gr_post` | `gr_unified_post` |
| Cancel GR | `/purchasing/receipts/<pk>/cancel/` | `gr_cancel` | `gr_unified_cancel` |
| | | | |
| Create Invoice | `/purchasing/invoices/new/` | `invoice_form` | `invoice-create` |
| Edit Invoice | `/purchasing/invoices/<pk>/edit/` | `invoice_form` | `invoice-edit` |
| View Invoice | `/purchasing/invoices/<pk>/detail/` | `invoice_detail` | `invoice-detail` |
| Post Invoice | `/purchasing/invoices/<pk>/post/` | `invoice_post` | `invoice-post` |
| Reverse Invoice | `/purchasing/invoices/<pk>/reverse/` | `invoice_reverse` | `invoice-reverse` |
| Return Invoice | `/purchasing/invoices/<pk>/return/` | `invoice_return` | `invoice-return` |
| | | | |
| Create LC Doc | `/purchasing/invoices/<id>/landed-cost/new/` | `landed_cost_unified_form` | `landed_cost_unified_create` |
| Edit LC Doc | `/purchasing/invoices/<id>/landed-cost/<doc_id>/edit/` | `landed_cost_unified_form` | `landed_cost_unified_edit` |
| Allocate LC | `/purchasing/landed-cost/<doc_id>/allocate/` | `landed_cost_allocate` | `landed-cost-allocate` |
| Delete LC | `/purchasing/landed-cost/<doc_id>/delete/` | `landed_cost_delete` | `landed-cost-delete` |
| | | | |
| Create Return | `/purchasing/returns/new/` | `pr_unified_form` | `pr_unified_create` |
| Edit Return | `/purchasing/returns/<pk>/` | `pr_unified_form` | `pr_unified_edit` |
| Return from Invoice | `/purchasing/invoices/<id>/return/` | `pr_unified_form` | `pr_from_invoice` |

### Legacy/Fallback Routes (Kept for Compatibility)

| Purpose | URL Pattern | Note |
|---------|----------|------|
| PO List Page | `/purchasing/pos/table/` | Fallback - prefer `po_unified_create` |
| GR List Page | `/purchasing/grs/table/` | Fallback - prefer `gr_unified_create` |
| Invoice List | `/purchasing/invoices/table/` | Fallback - use for display only |
| LC List | `/purchasing/landed-cost/table/` | Fallback - use for display only |
| Workspace | `/purchasing/` | Legacy - redirects to invoice workspace |

---

## Permission Structure

All purchasing operations require specific Django permissions:

```python
# Purchase Orders
'purchasing.view_purchaseorder'          # View POs
'purchasing.add_purchaseorder'           # Create POs
'purchasing.change_purchaseorder'        # Approve/Send POs

# Goods Receipts
'purchasing.view_goodsreceipt'           # View GRs
'purchasing.add_goodsreceipt'            # Create GRs
'purchasing.change_goodsreceipt'         # Inspect/Post GRs

# Purchase Invoices
'purchasing.view_purchaseinvoice'        # View invoices
'purchasing.add_purchaseinvoice'         # Create invoices
'purchasing.change_purchaseinvoice'      # Post invoices
'purchasing.delete_purchaseinvoice'      # Delete/Reverse invoices
```

**Setup:** These permissions are auto-created with the purchasing app. Add them to user roles via Django admin or your user management system.

---

## Key Features

### ✅ Real-Time Calculations
- Line totals, tax calculations, variance analysis
- All calculations performed client-side and server-side validated

### ✅ Multi-Currency Support
- Set currency per PO/Invoice
- Auto-converts between currencies using exchange rates
- GL entries use both base and invoice currencies

### ✅ GL Integration
- Automatic GL posting on document finalization
- Configurable GL accounts per line item
- Complete audit trail of GL entries
- Supports cost center and cost allocation

### ✅ Stock Ledger Integration
- Inventory updates on GR posting
- Quantity tracking: Ordered → Received → Invoiced
- Variance detection between expectations and actuals
- Stock value updates on landed cost allocation

### ✅ 3-Way Matching
- PO → GR → Invoice matching
- Variance alerts on discrepancies
- Prevents over-invoicing and duplicate payments

### ✅ Quality Control Tracking
- QC result tracking: Pass/Fail/Pending
- Batch and serial number support
- Expiry date tracking for perishables
- Inspection notes per line item

### ✅ Landed Cost Allocation
- Flexible allocation by value or quantity
- Real-time preview of cost distribution
- Automatic GL entries for cost allocation
- Cost per unit calculated and stored

### ✅ Audit & Compliance
- Complete change history via audit logs
- User attribution for all changes
- Status workflow enforcement
- Cannot edit finalized documents

---

## Templates & UI Components

### Main Form Templates

| Template | Purpose | Location |
|----------|---------|----------|
| `unified_form.html` | PO/GR combined form | `purchasing/templates/purchasing/` |
| `landed_cost_form.html` | LC entry with sidebar | `purchasing/templates/purchasing/` |
| `purchase_return_form.html` | Return confirmation | `purchasing/templates/purchasing/` |
| `po_detail_page.html` | PO detail view | `purchasing/templates/purchasing/` |
| `gr_detail_page.html` | GR detail view | `purchasing/templates/purchasing/` |
| `invoice_list_page.html` | Invoice list display | `purchasing/templates/purchasing/` |
| `landed_cost_list_page.html` | LC documents list | `purchasing/templates/purchasing/` |

### Partial Templates

| Template | Purpose |
|----------|---------|
| `_po_line_row.html` | Single PO line (editable) |
| `_gr_line_row.html` | Single GR line (editable) |
| `_landed_cost_line_row.html` | Single LC cost line |
| `invoice_detail.html` | Invoice summary display |
| `invoice_list.html` | Invoice list items |

---

## Services & Backend Integration

### Core Services

**PurchaseOrderService** (`purchasing/services/purchase_order_service.py`)
- `create_purchase_order()` - Create new PO with lines
- `approve_purchase_order()` - Approve PO for sending
- `mark_sent()` - Mark PO as sent to vendor
- `cancel_purchase_order()` - Cancel PO and reverse any GR impacts
- `close_if_fully_received()` - Auto-close when all goods received
- `update_po_line()` - Update line item
- `delete_po_line()` - Remove line item

**GoodsReceiptService** (`purchasing/services/goods_receipt_service.py`)
- `post_goods_receipt()` - Post receipt: update stock, generate GL entries
- `cancel_goods_receipt()` - Reverse stock and GL impacts
- `validate_3way_match()` - Check PO/GR/Invoice alignment

**ProcurementService** (`purchasing/services/procurement_service.py`)
- `post_purchase_invoice()` - Post invoice, generate GL entries
- `reverse_purchase_invoice()` - Reverse invoice GL entries
- `apply_landed_cost_document()` - Allocate costs and generate GL entries

### GL Integration Points

1. **PO Approval** → No GL entry (purchase commitment)
2. **GR Posting** → Debit Inventory, Credit AP (or Receiving account)
3. **Invoice Posting** → Debit AP Liability, Credit Expense/Inventory
4. **LC Allocation** → Debit specific GL accounts, Credit Inventory Variance

---

## Common Tasks

### Creating a Purchase Order

```
1. Sidebar: Click "Purchasing → New Purchase Order"
2. Fill form:
   - Vendor: Select supplier
   - PO Date: Set order date
   - Delivery Date: Set expected receipt date
   - Currency: Select currency
3. Add Line Items:
   - Product: Select or search
   - Qty: Enter quantity
   - Price: Enter unit price
   - GL Account: Select GL account for inventory
4. Click "Save as Draft"
5. Review totals
6. Click "Approve" to approve PO
7. Click "Send" to mark as sent to vendor
```

### Receiving Goods

```
1. Sidebar: Click "Purchasing → New Goods Receipt"
2. Search and select Purchase Order
3. System auto-fills line items from PO
4. For each line:
   - Enter Qty Received
   - Enter Qty Accepted (after QC)
   - Set QC Result: Pass/Fail/Pending
   - Add Batch # (if tracked)
   - Add Expiry Date (if perishable)
5. Click "Inspect" to mark QC complete
6. Click "Post" to update inventory
7. Verify stock ledger was updated
```

### Recording Purchase Invoice

```
1. Sidebar: Click "Purchasing → New Purchase Invoice"
2. Fill header:
   - Vendor: Select supplier
   - Invoice #: Enter supplier's invoice number
   - Invoice Date: Set invoice date
   - Currency: Select currency
3. Add line items (either link to GR or enter manual):
   - Description/Product
   - Quantity
   - Unit Price
   - GL Account
4. Verify totals match invoice
5. Click "Save as Draft"
6. Click "Post" to finalize and generate GL entries
7. Verify GL journal entry was created
```

### Allocating Landed Costs

```
1. From Purchase Invoice detail, click "Add Landed Cost"
2. Select allocation basis:
   - By Value: Allocate proportional to line amount
   - By Quantity: Allocate proportional to line quantity
3. Add cost lines:
   - Description: "Freight", "Customs Duty", etc.
   - Amount: Total cost
   - GL Account: Select GL account for cost
4. Review sidebar preview showing allocation per line
5. Click "Allocate"
6. System distributes costs and updates GL
7. Invoice line costs are now updated with allocated costs
```

---

## Troubleshooting

### Issue: "Cannot post GR - Stock account not set"

**Solution:** Ensure product has "Stock Ledger Account" configured in Inventory module.

### Issue: "GL entry not created"

**Solution:** Check that GL accounts exist in Chart of Accounts. View accounting GL posting logs for errors.

### Issue: "3-way match variance too high"

**Solution:** Review PO/GR/Invoice quantities and prices. Use variance report to identify discrepancies.

### Issue: "Landed cost allocation doesn't add up"

**Solution:** Verify allocation basis is correct (by value vs. by quantity). Check for rounding differences - costs are rounded to 2 decimals per accounting rules.

---

## Migration from Legacy System

### Old Location → New Location

| Old Path | Old Name | New Path | New Name |
|----------|----------|----------|----------|
| `/accounting/vendor-bills/new/` | vendor_bill_create | `/purchasing/invoices/new/` | invoice-create |
| `/purchasing/pos/table/` | po_table | `/purchasing/pos/table/` | po_table (same - fallback) |
| `/purchasing/grs/table/` | gr_table | `/purchasing/grs/table/` | gr_table (same - fallback) |

### Redirects Active

- `accounting:vendor_bill_create` → Shows deprecation message and redirects to `purchasing:invoice-create`
- Old bookmarks/links still work but show info message

### Data Preservation

- All existing POs, GRs, Invoices remain unchanged
- No data migration needed
- Old views still accessible for compatibility

---

## Performance Optimization

### Database Queries

All list views use:
- `select_related()` for vendor/supplier data
- `prefetch_related()` for line items
- Pagination (500 items max per list)

### Caching

- GL account lists cached for 1 hour
- Product lists cached for 30 minutes
- User organization cached for session

### Frontend

- Real-time calculations via JavaScript (no server round-trip)
- HTMX for partial page updates (no full page reload)
- Minimal CSS/JS - uses Bootstrap 5 + simple animations

---

## Monitoring & Alerts

### Key Metrics to Monitor

1. **Purchase Order Aging** - POs pending receipt > 30 days
2. **GR Variance** - Received vs. Ordered differences > 5%
3. **Invoice Variance** - Invoice vs. GR amount differences > 2%
4. **GL Posting Errors** - Any failed GL entries
5. **3-Way Match Failures** - Unable to match invoices

### Audit Logging

All changes logged to AuditLog table:
- View audit trail: `accounting:audit_log_list`
- Filter by content type: "Purchase Order", "Goods Receipt", "Purchase Invoice"
- Track user changes and timestamps

---

## Deployment Checklist

- [ ] Database migrations applied (if any)
- [ ] Static files collected (`python manage.py collectstatic`)
- [ ] Permissions created in admin for user roles
- [ ] GL accounts configured in Chart of Accounts
- [ ] Warehouses created in Inventory module
- [ ] Test PO/GR/Invoice flow end-to-end
- [ ] Verify GL entries created correctly
- [ ] Test landed cost allocation
- [ ] Verify stock ledger updates
- [ ] Train users on new sidebar navigation
- [ ] Disable old vendor bill entry link (optional)
- [ ] Monitor first week for errors and GL discrepancies

---

## Support & Documentation

For detailed technical information, see:
- `UNIFIED_PURCHASING_FLOW.md` - Technical architecture
- `PURCHASING_QUICKSTART.md` - Developer quick start
- `IMPLEMENTATION_SUMMARY.md` - Implementation details
- `ARCHITECTURE.md` - System architecture diagrams

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.0 | 2025-12-20 | Unified workflow, cleaned sidebar, removed legacy routes |
| 1.0 | 2025-11-15 | Initial implementation with separate PO/GR/Invoice flows |

---

**Ready for Production** ✅
