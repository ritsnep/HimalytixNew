# Inventory Pricing & Vendor/Customer Rate History - Patch Plan

## Overview
This patch introduces scalable, multi-tenant-compliant pricing features to the Inventory module, including:
- Vendor purchase rate history
- Vendor/customer-specific purchase/sales rates
- UI and API for viewing and managing these rates
- Auditability and extensibility, reusing existing ERP patterns

---

## File-by-File Change Plan

### 1. ERP/inventory/models.py
- **Add `VendorPriceHistory` model**:
  - Fields: org_id (FK), vendor (FK), product (FK), purchase_rate, currency, quantity, doc_ref, doc_date, created_at, created_by
  - Indexes: (org_id, vendor, product, doc_date)
- **Add `CustomerPriceHistory` model**:
  - Fields: org_id (FK), customer (FK), product (FK), sales_rate, currency, quantity, doc_ref, doc_date, created_at, created_by
  - Indexes: (org_id, customer, product, doc_date)

### 2. ERP/inventory/services.py
- **Add service methods**:
  - `record_vendor_price_history(vendor, product, rate, ...)`
  - `record_customer_price_history(customer, product, rate, ...)`
  - `get_vendor_price_history(product, vendor, org, limit=20)`
  - `get_customer_price_history(product, customer, org, limit=20)`
- **Integrate with purchase receipt and sales invoice posting** to auto-record rates

### 3. ERP/inventory/views.py
- **Add views**:
  - List/detail views for vendor/customer price history (HTMX partials for product/vendor/customer detail pages)
  - Endpoints to view historical rates per product/vendor/customer

### 4. ERP/inventory/templates/Inventory/
- **Add partials**:
  - `product_vendor_price_history.html`
  - `product_customer_price_history.html`
  - Show last N rates, with date, quantity, rate, doc link
  - HTMX modals/tabs for drilldown

### 5. ERP/inventory/api/views.py & serializers.py
- **Add API endpoints and serializers**:
  - For vendor/customer price history (list, filter by product/vendor/customer, create)

### 6. ERP/inventory/tests.py
- **Add tests**:
  - Unit tests for service logic (recording/fetching rates)
  - Integration tests for UI/API flows (HTMX, permissions, org scoping)

### 7. ERP/inventory/migrations/
- **Create reversible migrations** for new models

---

## Example Diff (ERP/inventory/models.py)

```diff
+class VendorPriceHistory(models.Model):
+    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
+    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT)
+    product = models.ForeignKey(Product, on_delete=models.PROTECT)
+    purchase_rate = models.DecimalField(max_digits=19, decimal_places=4)
+    currency = models.CharField(max_length=8)
+    quantity = models.DecimalField(max_digits=15, decimal_places=4)
+    doc_ref = models.CharField(max_length=64, blank=True, null=True)
+    doc_date = models.DateField()
+    created_at = models.DateTimeField(auto_now_add=True)
+    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
+    class Meta:
+        indexes = [models.Index(fields=['organization', 'vendor', 'product', 'doc_date'])]
+        ordering = ['-doc_date']

+class CustomerPriceHistory(models.Model):
+    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
+    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
+    product = models.ForeignKey(Product, on_delete=models.PROTECT)
+    sales_rate = models.DecimalField(max_digits=19, decimal_places=4)
+    currency = models.CharField(max_length=8)
+    quantity = models.DecimalField(max_digits=15, decimal_places=4)
+    doc_ref = models.CharField(max_length=64, blank=True, null=True)
+    doc_date = models.DateField()
+    created_at = models.DateTimeField(auto_now_add=True)
+    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
+    class Meta:
+        indexes = [models.Index(fields=['organization', 'customer', 'product', 'doc_date'])]
+        ordering = ['-doc_date']
```

---

## Migration & Rollback
- Migration: Add new tables, no destructive changes
- Rollback: Drop new tables

---

## Review Checklist
- [ ] Multi-tenant enforced (org_id)
- [ ] Permission checks
- [ ] Audit fields present
- [ ] No breaking changes
- [ ] Tests included
- [ ] Rollback path clear

---

**End of patch/notes.**
