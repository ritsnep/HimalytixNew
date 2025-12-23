# Purchase Invoice Mockup Backend Integration Guide

## Overview
This document provides a comprehensive guide for integrating the `purchaseinvoice_mockup.html` with the Django backend. The integration will transform the static mockup into a fully functional purchase invoice entry form using HTMX for dynamic interactions.

## Architecture
- **Frontend**: HTML/JS with HTMX for AJAX calls
- **Backend**: Django views calling service layer
- **Services**: Dedicated services for business logic
- **Database**: Existing ERP models (PurchaseInvoice, PurchaseInvoiceLine, etc.)

## Prerequisites
- All services implemented (ProductService, VendorService, PricingService, etc.)
- HTMX library loaded in templates
- Django URL patterns configured
- CSRF protection enabled

## 1. URL Configuration
Add these URLs to `accounting/urls.py`:

```python
from django.urls import path
from . import views

urlpatterns = [
    # Purchase Invoice URLs
    path('purchase-invoice/new/', views.purchase_invoice_form, name='purchase_invoice_form'),
    path('purchase-invoice/load-vendor/<int:vendor_id>/', views.load_vendor_details, name='load_vendor_details'),
    path('purchase-invoice/load-product/<int:product_id>/', views.load_product_details, name='load_product_details'),
    path('purchase-invoice/calculate-totals/', views.calculate_invoice_totals, name='calculate_totals'),
    path('purchase-invoice/save/', views.save_purchase_invoice, name='save_purchase_invoice'),
    path('purchase-invoice/apply-order/<int:order_id>/', views.apply_purchase_order, name='apply_order'),
    path('purchase-invoice/next-voucher-no/', views.get_next_voucher_number, name='next_voucher_no'),
]
```

## 2. View Implementation
Create `accounting/views/purchase_invoice_views.py`:

```python
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from accounting.services.purchase_invoice_service import PurchaseInvoiceService
from accounting.services.vendor_service import VendorService
from accounting.services.product_service import ProductService
from accounting.services.pricing_service import PricingService
from accounting.services.agent_service import AgentService
from accounting.services.validation_service import ValidationService
from accounting.services.notification_service import NotificationService
from accounting.services.document_sequence_service import DocumentSequenceService
import json

def purchase_invoice_form(request):
    """Render the main purchase invoice form"""
    context = {
        'voucher_prefix': 'PB',
        'fiscal_year': '82/83',  # Get from FiscalYearService
        'suppliers': VendorService.get_vendors_for_dropdown(),
        'purchase_accounts': [],  # Load from ChartOfAccountService
        'agents': AgentService.get_agents_for_dropdown(),
        'areas': AgentService.get_areas_for_dropdown(),
        'orders': [],  # Load pending POs/GRNs
        'terms': [],  # Load from TermsService
        'godowns': [],  # Load from WarehouseService
        'payment_ledgers': [],  # Load from ChartOfAccountService
    }
    return render(request, 'accounting/purchaseinvoice_form.html', context)

def load_vendor_details(request, vendor_id):
    """Load vendor details via HTMX"""
    try:
        details = VendorService.get_vendor_details(vendor_id)
        agent_info = AgentService.auto_select_agent_for_vendor(vendor_id)

        return JsonResponse({
            'success': True,
            'supplier_info': f"Balance: NPR {details['balance']:.2f} | PAN: {details['pan']} | Credit Limit: NPR {details['credit_limit']:.2f}",
            'agent_id': agent_info['agent_id'],
            'area_id': agent_info['area_id'],
            'due_days': 30,  # From vendor payment terms
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def load_product_details(request, product_id):
    """Load product details for line item"""
    try:
        product = ProductService.get_product_details(product_id)
        vendor_id = request.GET.get('vendor_id')
        pricing = {'standard_price': product['standard_price']}
        if vendor_id:
            pricing = PricingService.get_pricing_for_party(product_id, int(vendor_id))

        return JsonResponse({
            'success': True,
            'hs_code': product['hs_code'],
            'description': product['description'],
            'unit': product['unit'],
            'vat_applicable': product['vat_applicable'],
            'rate': pricing['party_price'],
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@require_POST
def calculate_invoice_totals(request):
    """Calculate and return invoice totals"""
    try:
        data = json.loads(request.body)
        totals = PurchaseInvoiceService.calculate_totals(data['line_items'], data.get('header_discount', {}))

        return JsonResponse({
            'success': True,
            'totals': totals,
            'in_words': PurchaseInvoiceService.amount_to_words(totals['grand_total']),
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@require_POST
def save_purchase_invoice(request):
    """Save the purchase invoice"""
    try:
        data = json.loads(request.body)

        # Validate data
        errors = ValidationService.validate_purchase_invoice_data(data)
        if errors:
            return JsonResponse({'success': False, 'errors': errors})

        # Create invoice
        invoice = PurchaseInvoiceService.create_invoice(data, request.user)

        # Send notifications if needed
        if invoice.amount > 100000:  # High value threshold
            NotificationService.send_approval_notification(
                invoice.id, invoice.get_approvers(), 'purchase_invoice'
            )

        return JsonResponse({
            'success': True,
            'invoice_id': invoice.id,
            'message': 'Invoice saved successfully'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def apply_purchase_order(request, order_id):
    """Apply purchase order lines to invoice"""
    try:
        order_lines = PurchaseInvoiceService.get_order_lines_for_invoice(order_id)
        return JsonResponse({'success': True, 'lines': order_lines})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def get_next_voucher_number(request):
    """Get next voucher number"""
    try:
        next_no = DocumentSequenceService.get_next_number('purchase_invoice', 'PB')
        return JsonResponse({'success': True, 'voucher_no': next_no})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
```

## 3. Template Updates
Update `purchaseinvoice_mockup.html` to use HTMX:

### Header Section Updates:
```html
<!-- Supplier Selection -->
<select class="form-select form-select-sm" id="party_ledger_id"
        hx-get="/accounting/purchase-invoice/load-vendor/0/"
        hx-target="#supplier_info"
        hx-swap="innerHTML"
        name="party_ledger_id">
  <option value="">— Select Supplier —</option>
  {% for supplier in suppliers %}
  <option value="{{ supplier.id }}">{{ supplier.name }}</option>
  {% endfor %}
</select>

<!-- Supplier Info Display -->
<div class="form-control form-control-sm readonly" id="supplier_info">
  Please select Supplier Name to view balance and details.
</div>
```

### Line Items Updates:
```html
<!-- Product Selection -->
<select class="form-select form-select-sm line-item" data-field="item_id"
        hx-get="/accounting/purchase-invoice/load-product/0/"
        hx-target="closest tr"
        hx-swap="none"
        hx-include="[name='party_ledger_id']">
  <option value="">— Select Item —</option>
  {% for item in items %}
  <option value="{{ item.id }}">{{ item.name }}</option>
  {% endfor %}
</select>
```

### Totals Calculation:
```html
<!-- Auto-calculate on changes -->
<div hx-post="/accounting/purchase-invoice/calculate-totals/"
     hx-trigger="change from:#itemsTbody, keyup from:#itemsTbody"
     hx-target="#totals-panel"
     hx-swap="innerHTML">
  <!-- Existing totals HTML -->
</div>
```

### Form Submission:
```html
<form hx-post="/accounting/purchase-invoice/save/"
      hx-target="#messages"
      hx-swap="innerHTML"
      enctype="multipart/form-data">
  <!-- Form content -->
</form>
```

## 4. JavaScript Enhancements
Update the mockup's JavaScript to work with HTMX:

```javascript
// Remove manual event listeners, let HTMX handle them
// Update URLs to use Django URLs
const API_BASE = '/accounting/purchase-invoice/';

// Update load functions to use HTMX attributes instead of fetch
function updateVendorInfo(vendorId) {
  // HTMX will handle this automatically
}

// Update product loading
function updateProductInfo(productId, row) {
  // HTMX handles via hx-get
}

// Update totals calculation
function recalcAll() {
  // Trigger HTMX request instead of manual calculation
  htmx.trigger('#totals-panel', 'change');
}
```

## 5. Service Integration Details

### Product Selection Flow:
1. User selects product → HTMX GET to `load_product_details`
2. View calls `ProductService.get_product_details()`
3. Returns JSON with unit, HS code, description, VAT, pricing
4. HTMX updates form fields
5. Triggers totals recalculation

### Vendor Selection Flow:
1. User selects vendor → HTMX GET to `load_vendor_details`
2. View calls `VendorService.get_vendor_details()` and `AgentService.auto_select_agent_for_vendor()`
3. Returns JSON with balance, agent, area
4. HTMX updates supplier info and auto-selects agent/area

### Totals Calculation Flow:
1. Line item changes → HTMX POST to `calculate_totals`
2. View calls `PurchaseInvoiceService.calculate_totals()`
3. Returns JSON with all totals breakdowns
4. HTMX updates totals panel

### Save Flow:
1. User clicks save → HTMX POST to `save`
2. View validates with `ValidationService.validate_purchase_invoice_data()`
3. Creates invoice with `PurchaseInvoiceService.create_invoice()`
4. Posts to GL with `PostingService`
5. Sends notifications with `NotificationService`
6. Returns success/error response

## 6. Error Handling
- Use Django's messaging framework for user notifications
- HTMX will automatically handle 4xx/5xx responses
- Add error displays in template:

```html
<div id="messages">
  {% if messages %}
    {% for message in messages %}
      <div class="alert alert-{{ message.tags }}">{{ message }}</div>
    {% endfor %}
  {% endif %}
</div>
```

## 7. Security Considerations
- All HTMX requests include CSRF tokens
- Validate user permissions in views
- Sanitize all input data
- Use Django's authentication decorators

## 8. Performance Optimizations
- Cache frequently accessed data (products, vendors)
- Use select_related/prefetch_related in services
- Implement pagination for large dropdowns
- Add debouncing for rapid user input

## 9. Testing Strategy
- Unit tests for each service method
- Integration tests for HTMX endpoints
- End-to-end tests for complete workflows
- Load testing for concurrent invoice creation

## 10. Deployment Checklist
- [ ] Services implemented and tested
- [ ] URLs configured
- [ ] Templates updated with HTMX
- [ ] JavaScript refactored
- [ ] Error handling implemented
- [ ] Security measures in place
- [ ] Performance optimized
- [ ] Tests passing
- [ ] Documentation updated

This integration transforms the static mockup into a production-ready, dynamic web application with robust backend services.