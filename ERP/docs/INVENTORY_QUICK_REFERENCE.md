# Inventory Module - Quick Reference Guide
**Last Updated:** December 4, 2025

---

## 🚀 Quick Start

### Access Inventory Module
```
Base URL: /inventory/
Requires: Active organization + Inventory app permission
```

### Main Workflows

| Workflow | URL | Purpose |
|----------|-----|---------|
| **Master Data** | | |
| Manage Products | `/inventory/products/` | CRUD operations on products |
| Manage Categories | `/inventory/categories/` | Organize products by type |
| Manage Warehouses | `/inventory/warehouses/` | Configure storage locations |
| Manage Locations | `/inventory/locations/` | Define bins/slots within warehouses |
| Manage Price Lists | `/inventory/pricelists/` | Set customer pricing |
| **Operations** | | |
| View Stock Levels | `/inventory/stock/` | Current inventory report |
| View Ledger | `/inventory/ledger/` | Transaction history |
| Record Stock Movement | `/inventory/stock/` | (In/Out transactions) |
| **Picking & Shipping** | | |
| Manage Pick Lists | `/inventory/picklists/` | Prepare orders for shipment |
| Manage Shipments | `/inventory/shipments/` | Track inter-warehouse transfers |
| Manage RMAs | `/inventory/rmas/` | Process customer returns |
| **Manufacturing** | | |
| Manage BOMs | `/inventory/boms/` | Define product components |

---

## 📝 Form Fields Reference

### **Product Form** (16 fields)
```
Code (auto)          UOM              Sale Price
Name (required)      Currency Code    Cost Price
Description          Category         Income Account
                     Inventory Item?  COGS Account
                     Min Order Qty    Inventory Account
                     Reorder Level    Barcode
                     Preferred Vendor SKU
```

### **Warehouse Form** (7 fields)
```
Code (auto)          City             Inventory Account
Name (required)      Country Code     Active?
Address Line 1
```

### **Location Form** (5 fields)
```
Warehouse (required)  Code (required)  Active?
Name                  Type (storage/staging/QC)
```

### **Stock Transaction Form** (8 fields)
```
Transaction Type     Product          Reference
Warehouse           Quantity         Notes
Location            Batch/Serial
```

---

## 🔐 Permissions Model

All permissions follow pattern: `Inventory.<action>_<model>`

### **Model-Level Permissions**
```
view_productcategory      → Read-only access to categories
add_productcategory       → Create new categories
change_productcategory    → Edit existing categories
delete_productcategory    → Delete categories

(Same pattern for: product, warehouse, location, pricelist, 
 picklist, shipment, rma, billofmaterial)
```

### **Permission Checking**
```python
# In templates:
{% if can_add %}
  <a href="...">Add Item</a>
{% endif %}

# In views: Automatic via PermissionRequiredMixin
permission_required = 'Inventory.add_product'
```

---

## 📊 Data Relationships

```
Organization (Tenant)
├── ProductCategory (hierarchical via MPPT)
│   └── Product
│       ├── StockLedger (transaction history)
│       ├── InventoryItem (current levels)
│       └── PriceList
│           └── PriceListItem
├── Warehouse
│   ├── Location
│   ├── PickList
│   │   └── PickListLine
│   ├── Shipment
│   │   └── ShipmentLine
│   └── RMA
│       └── RMALine
└── BillOfMaterial
    ├── BillOfMaterialItem
    └── (references components as Products)
```

---

## 🎨 UI Patterns

### **List View Pattern**
```html
{% extends "components/base/list_base.html" %}
- Breadcrumbs
- Title + Subtitle
- Add/Filter buttons
- DataTable with pagination
- Responsive on mobile
```

### **Form Pattern**
```html
{% extends "components/base/form_base.html" %}
- Breadcrumbs
- Form title + subtitle
- Field-level errors
- Form field component include
- Save/Cancel buttons
```

### **Detail Pattern**
```html
{% extends "components/base/detail_base.html" %}
- Breadcrumbs
- Read-only field display
- Related data tables
- Edit/Delete action buttons
- Permission-gated buttons
```

### **Delete Confirmation Pattern**
```html
{% extends "components/base/confirm_delete.html" %}
- Confirmation message
- Warning about data loss
- Cancel/Confirm buttons
```

---

## 🔗 API Endpoints

### **List Endpoints** (GET)
```
/inventory/categories/
/inventory/products/
/inventory/warehouses/
/inventory/locations/
/inventory/pricelists/
/inventory/picklists/
/inventory/shipments/
/inventory/rmas/
/inventory/boms/
```

### **Create Endpoints** (GET form, POST save)
```
/inventory/categories/create/
/inventory/products/create/
... (same pattern for all models)
```

### **Detail Endpoints** (GET)
```
/inventory/categories/<pk>/
/inventory/products/<pk>/
... (same pattern for all models)
```

### **Edit Endpoints** (GET form, POST save)
```
/inventory/categories/<pk>/edit/
/inventory/products/<pk>/edit/
... (same pattern for all models)
```

### **Delete Endpoints** (GET confirmation, POST delete)
```
/inventory/categories/<pk>/delete/
/inventory/products/<pk>/delete/
... (same pattern for all models)
```

### **Report Endpoints** (GET with filters)
```
/inventory/stock/              - Current levels report
  ?warehouse=<id>             - Filter by warehouse
  ?product=<id>               - Filter by product

/inventory/ledger/            - Transaction history
  ?warehouse=<id>
  ?product=<id>
  ?start_date=YYYY-MM-DD
  ?end_date=YYYY-MM-DD
```

---

## 🛠️ Common Tasks

### **Add a New Product**
1. Go to `/inventory/products/`
2. Click "Add Product" button
3. Fill form:
   - Code (auto-generated as PROD001)
   - Name (required)
   - Category (optional)
   - UOM, pricing, GL accounts
4. Click "Save Product"

### **Record Stock Receipt**
1. Go to `/inventory/stock/` report
2. Click "Record Transaction" button
3. Select:
   - Transaction Type: Receipt
   - Warehouse: [select warehouse]
   - Product: [select product]
   - Quantity: [enter qty]
4. Click "Save Transaction"

### **View Stock Levels**
1. Go to `/inventory/stock/`
2. (Optional) Filter by warehouse or product
3. Click "Filter" to apply
4. View table with quantity, cost, value

### **Create Pick List for Order**
1. Go to `/inventory/picklists/`
2. Click "Add Pick List" button
3. Select warehouse
4. Add lines (product, qty required, location)
5. Click "Save"

### **Ship to Another Warehouse**
1. Go to `/inventory/shipments/`
2. Click "Add Shipment" button
3. Select from/to warehouses
4. Add shipment lines (product, qty)
5. Enter ship date
6. Click "Save Shipment"

---

## 📋 Field Validation Rules

### **Code Fields**
- Required: Yes
- Unique: Within organization
- Auto-generated: Yes (configurable prefix)
- Pattern: Alphanumeric + underscore

### **Price Fields**
- Type: Decimal(19, 4)
- Precision: Up to 4 decimal places
- Example: 1234.5678

### **Quantity Fields**
- Type: Decimal(15, 4)
- Precision: Up to 4 decimal places
- Example: 100.5000

### **GL Account Fields**
- Required for inventory items: YES
- Type: ForeignKey to ChartOfAccount
- Validation: Must be from same organization

### **Date Fields**
- Format: YYYY-MM-DD
- Picker: Bootstrap datepicker
- Example: 2025-12-04

---

## 🐛 Troubleshooting

### **"Select an active organization" Error**
- Solution: Go to dashboard and select organization
- Link: `/usermanagement/select_organization/`

### **"You don't have permission" Error**
- Solution: Check with administrator for inventory permissions
- Permission needed: `Inventory.<action>_<model>`

### **Form shows "This field is required"**
- Inventory items must have:
  - GL Inventory Account
  - GL COGS Account
  - Category (recommended)

### **Delete button is disabled/missing**
- Solution: Check delete permission
- Permission needed: `Inventory.delete_<model>`
- Also check if model has dependent records

### **Code field shows "This value already exists"**
- Solution: Code must be unique within organization
- Try with different code or check if already created

### **Barcode not scanning**
- Ensure browser supports barcode input
- Check if product has barcode field populated
- May require JavaScript barcode reader plugin

---

## 📱 Mobile Experience

### **Supported Features on Mobile**
- ✅ List views (responsive tables)
- ✅ Form entry (single column layout)
- ✅ Detail views (stacked layout)
- ✅ Filters (collapsible on small screens)

### **Not Optimized for Mobile**
- Barcode scanning (use desktop scanner)
- Large data exports (use desktop)
- Complex multi-line forms (use desktop for initial setup)

---

## 🔄 Data Flow Examples

### **Stock Receipt Process**
```
User Records Receipt
    ↓
StockTransaction created
    ↓
Service Layer validates
    ↓
StockLedger entry created (immutable)
    ↓
InventoryItem snapshot updated
    ↓
GL Entry created (auto, if configured)
```

### **Product Creation Process**
```
Form submitted with product data
    ↓
BootstrapFormMixin validates
    ↓
Organization auto-assigned
    ↓
Code auto-generated (if empty)
    ↓
User tracking (created_by)
    ↓
Product saved to database
    ↓
Redirect to product list
```

### **Permission Check Flow**
```
User requests list view
    ↓
BaseListView.dispatch() called
    ↓
get_organization() from UserOrganizationMixin
    ↓
PermissionUtils.has_permission() checked
    ↓
If no permission → redirect to dashboard
    ↓
If permission granted → get_queryset() filters by org
```

---

## 📚 Related Documentation

- **Status Report:** `INVENTORY_STATUS_REPORT.md` - Detailed analysis
- **Implementation:** `INVENTORY_IMPLEMENTATION_COMPLETE.md` - Session summary
- **App README:** `Inventory/README.md` - Integration steps
- **Architecture:** `accounting_architecture.md` - Similar module pattern

---

## 📞 Support

For issues or questions:
1. Check this quick reference first
2. Review `INVENTORY_STATUS_REPORT.md` for details
3. Check app `README.md` for integration info
4. Contact development team with specific error messages

---

**Module Status:** ✅ Production Ready (MVP)  
**Last Updated:** December 4, 2025  
**Version:** 1.0 Complete
