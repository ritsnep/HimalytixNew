# IRD Sales Invoice System - Quick Start Guide

## 🚀 Quick Setup (5 Minutes)

### Step 1: Run Database Migration
```bash
cd c:\PythonProjects\Himalytix\ERP
python manage.py migrate accounting
```

### Step 2: Configure IRD Settings

Add to your `settings.py`:
```python
# At the end of settings.py
from accounting.settings.ird_settings import *

# Environment-based configuration
import os
IRD_API_URL = os.getenv('IRD_API_URL', 'https://test.ird.gov.np/api/v1')
IRD_USERNAME = os.getenv('IRD_USERNAME', '')
IRD_PASSWORD = os.getenv('IRD_PASSWORD', '')
IRD_SELLER_PAN = os.getenv('IRD_SELLER_PAN', '')
IRD_INTEGRATION_ENABLED = True
IRD_TESTING_MODE = True  # Set to False for production
```

### Step 3: Add URL Patterns

In your main `urls.py`:
```python
from django.urls import path, include

urlpatterns = [
    # ... existing patterns ...
    path('accounting/', include('accounting.urls.invoice_urls')),
]
```

### Step 4: Install Required Packages
```bash
pip install qrcode[pil] pillow requests weasyprint
```

### Step 5: Create Environment File

Create `.env` in your project root:
```bash
IRD_API_URL=https://test.ird.gov.np/api/v1
IRD_USERNAME=your_test_username
IRD_PASSWORD=your_test_password
IRD_SELLER_PAN=999999999
IRD_TESTING_MODE=true
```

## 📋 Files Created

### 1. Database Migration
- `accounting/migrations/0154_salesinvoice_ird_fields.py`
- `accounting/migrations/0155_add_missing_ird_fields.py`

Note: If your database already contains some IRD columns, you may need to fake-apply the first migration:

```powershell
python manage.py migrate accounting --fake 0154
python manage.py migrate accounting
```

### 2. Views & Services
- `accounting/views/ird_invoice_views.py` - All view logic
- `accounting/services/ird_ebilling.py` - IRD service (already exists)

### 3. URL Configuration
- `accounting/urls/invoice_urls.py` - URL routing

### 4. Templates
- `accounting/templates/accounting/sales_invoice_detail.html`
- `accounting/templates/accounting/invoice_print.html`
- `accounting/templates/accounting/invoice_cancel_confirm.html`
- `accounting/templates/accounting/ird_dashboard.html`

### 5. Configuration
- `accounting/settings/ird_settings.py` - All IRD settings

### 6. Documentation
- `accounting/IRD_INVOICE_SYSTEM_README.md` - Complete documentation

## 🔧 Testing the System

### 1. Access Invoice List
```
http://localhost:8000/accounting/invoices/
```

### 2. Create Test Invoice
1. Click "New Invoice"
2. Fill in customer details
3. Add at least one line item
4. Save as draft

### 3. Post Invoice
1. Open invoice detail
2. Click "Post Invoice"
3. Optionally check "Auto-submit to IRD"

### 4. Submit to IRD (Manual)
1. Click "Submit to IRD" button
2. Wait for confirmation
3. View QR code in invoice detail (if IRD returned success)

If IRD returns an HTML rejection (common when credentials are missing or IP is not whitelisted), check `scripts/ird_response_*.txt` and `scripts/ird_payload_*.json` for the raw request/response saved during debug runs.

### 5. Print Invoice
1. Click "Print" button
2. QR code will be displayed (if IRD-synced)
3. Reprint count tracked automatically

## 📊 Key URLs

| Feature | URL Pattern |
|---------|------------|
| Invoice List | `/accounting/invoices/` |
| Create Invoice | `/accounting/invoices/create/` |
| Invoice Detail | `/accounting/invoices/<id>/` |
| Edit Invoice | `/accounting/invoices/<id>/edit/` |
| Post Invoice | `/accounting/invoices/<id>/post/` |
| Submit to IRD | `/accounting/invoices/<id>/submit-ird/` |
| Print Invoice | `/accounting/invoices/<id>/print/` |
| Cancel in IRD | `/accounting/invoices/<id>/cancel-ird/` |
| IRD Dashboard | `/accounting/ird-dashboard/` |
| QR Code Image | `/accounting/invoices/<id>/qr-code/` |
| Batch Submit | `/accounting/invoices/batch-submit-ird/` |

Note: There are two invoice entry flows in the project:
- Subscription invoices: `/billing/invoices/create/` (subscription-managed invoices)
- HTMX one-off invoice entry: `/billing/invoice/create/` (single invoice entry). If your templates use `{% url 'invoice_save' %}` update them to the namespaced form `{% url 'billing:invoice_save' %}` so they resolve correctly when `billing` is included with a namespace.

## 🎯 Common Tasks

### Task 1: Create and Submit Invoice
```python
from accounting.models import SalesInvoice, Customer
from accounting.services.ird_ebilling import IRDEBillingService

# Create invoice
invoice = SalesInvoice.objects.create(
    organization=org,
    customer=customer,
    invoice_date=date.today(),
    due_date=date.today() + timedelta(days=30),
    currency=currency,
)

# Add lines
invoice.lines.create(
    line_number=1,
    description="Product A",
    quantity=10,
    unit_price=100,
    revenue_account=account,
)

# Recompute totals
invoice.recompute_totals()

# Submit to IRD
ird_service = IRDEBillingService(org)
result = ird_service.submit_invoice(invoice)
print(result)
```

### Task 2: Batch Submit Pending Invoices
```python
from accounting.models import SalesInvoice
from accounting.services.ird_ebilling import IRDEBillingService

pending = SalesInvoice.objects.filter(
    status='posted',
    ird_status__isnull=True
)

ird_service = IRDEBillingService(organization)
for invoice in pending:
    result = ird_service.submit_invoice(invoice)
    print(f"{invoice.invoice_number}: {result['success']}")
```

### Task 3: Generate QR Code
```python
from accounting.services.ird_ebilling import IRDEBillingService

invoice = SalesInvoice.objects.get(invoice_number='INV-001')
ird_service = IRDEBillingService(organization)

# Generate QR data
qr_data = ird_service._generate_qr_data(invoice, {
    'acknowledgment_id': invoice.ird_ack_id,
    'signature': invoice.ird_signature
})

# Generate QR image
qr_image = ird_service.generate_qr_code_image(qr_data)
with open('invoice_qr.png', 'wb') as f:
    f.write(qr_image.getvalue())
```

## ⚠️ Important Notes

### Invoice Status Flow
```
Draft → Posted → IRD Synced → Printed
  ↓       ↓          ↓
 Edit   Submit   Cannot Edit
```

### IRD Integration Modes

**Testing Mode (IRD_TESTING_MODE=True)**
- Uses test IRD API
- No real tax implications
- Safe for development

**Production Mode (IRD_TESTING_MODE=False)**
- Uses live IRD API
- Real tax submissions
- Requires valid credentials

### Security Checklist
- ✅ Never commit credentials to git
- ✅ Use environment variables
- ✅ Enable SSL for production
- ✅ Encrypt sensitive data
- ✅ Regular backups

## 🐛 Troubleshooting

### Problem: Migration Fails
**Solution:**
```bash
python manage.py migrate accounting --fake 0154
python manage.py migrate accounting
```

### Problem: IRD API Connection Error
**Check:**
1. Internet connection
2. IRD_API_URL is correct
3. Firewall settings
4. IRD server status
5. IRD credentials and seller PAN (set via environment variables)
6. IRD test sandbox may require IP whitelisting or special headers/certs

If you see a non-JSON HTML response that says "Request Rejected", it's typically the IRD gateway rejecting the request before payload validation. Capture the raw request/response (see `scripts/`) and contact IRD support or provide valid test credentials.

### Problem: QR Code Not Generating
**Verify:**
1. `qrcode` package installed
2. Invoice is IRD-synced
3. `ird_ack_id` exists
4. PIL/Pillow installed

### Problem: Template Not Found
**Solution:**
```bash
# Verify template directory structure
accounting/
  templates/
    accounting/
      sales_invoice_list.html
      sales_invoice_detail.html
      invoice_print.html
      ...
```

## 📞 Support

For issues or questions:
1. Check `IRD_INVOICE_SYSTEM_README.md` for detailed documentation
2. Review Django logs: `logs/django.log`
3. Check IRD logs: `logs/ird/`
4. Contact system administrator

## 🎉 Success Indicators

You know the system is working when:
- ✅ Invoices list displays correctly
- ✅ New invoices can be created
- ✅ IRD submission returns success
- ✅ QR codes are generated
- ✅ Reprint count increments
- ✅ Dashboard shows statistics

## 📈 Next Steps

After setup:
1. **Configure Production IRD Credentials**
2. **Set up automated backups**
3. **Train users on invoice workflow**
4. **Test batch submission**
5. **Configure email notifications**
6. **Set up monitoring/alerts**

---

**Ready to go!** Start by accessing `/accounting/invoices/` in your browser.
