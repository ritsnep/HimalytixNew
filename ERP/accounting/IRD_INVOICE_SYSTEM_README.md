# IRD E-Billing Integrated Sales Invoice System

## Overview

This is a comprehensive sales invoice entry system integrated with Nepal's Inland Revenue Department (IRD) e-billing system. It provides real-time invoice submission, QR code generation, and complete compliance with Nepal tax regulations.

## Features

### Core Features
- ✅ Complete sales invoice CRUD operations
- ✅ Multi-line invoice entry with dynamic forms
- ✅ Real-time IRD e-billing integration
- ✅ Automatic QR code generation for verified invoices
- ✅ Invoice posting and journal entry creation
- ✅ Batch IRD submission support
- ✅ Invoice cancellation in IRD system
- ✅ Print/reprint tracking for audit compliance
- ✅ Comprehensive audit trail

### IRD Compliance Features
- 🔐 Secure API integration with IRD servers
- 📱 QR code generation for invoice verification
- 🔄 Real-time and batch submission modes
- 📊 IRD status dashboard and reporting
- ⏱️ Fiscal year conversion (Gregorian to Bikram Sambat)
- 🔒 Locked editing for IRD-synced invoices
- 📝 Cancellation reason tracking
- 🖨️ Reprint count monitoring

## Installation

### 1. Database Migration

Run the migration to add IRD fields to the SalesInvoice model:

```bash
python manage.py migrate accounting
```

This will create the following fields:
- `ird_signature` - IRD digital signature
- `ird_ack_id` - IRD acknowledgment ID
- `ird_status` - Sync status (pending/synced/failed/cancelled)
- `ird_last_response` - Last IRD API response
- `ird_last_submitted_at` - Submission timestamp
- `ird_reprint_count` - Number of reprints
- `ird_last_printed_at` - Last print timestamp
- `ird_fiscal_year_code` - Bikram Sambat fiscal year
- `ird_is_realtime` - Real-time submission flag
- `ird_digital_payment_amount` - Digital payment tracking
- `ird_digital_payment_txn_id` - Payment transaction ID

### 2. Settings Configuration

Add IRD settings to your `settings.py`:

```python
# IRD E-Billing Settings
from accounting.settings.ird_settings import *

# Override with environment variables (recommended)
import os

IRD_API_URL = os.getenv('IRD_API_URL', 'https://test.ird.gov.np/api/v1')
IRD_USERNAME = os.getenv('IRD_USERNAME', '')
IRD_PASSWORD = os.getenv('IRD_PASSWORD', '')
IRD_SELLER_PAN = os.getenv('IRD_SELLER_PAN', '')
IRD_TESTING_MODE = os.getenv('IRD_TESTING_MODE', 'true').lower() == 'true'
IRD_INTEGRATION_ENABLED = True
```

### 3. Environment Variables

Create a `.env` file:

```bash
# IRD Configuration
IRD_API_URL=https://test.ird.gov.np/api/v1
IRD_USERNAME=your_ird_username
IRD_PASSWORD=your_ird_password
IRD_SELLER_PAN=your_pan_number
IRD_TESTING_MODE=true
IRD_INTEGRATION_ENABLED=true
```

### 4. URL Configuration

Add to your main `urls.py`:

```python
from django.urls import path, include

urlpatterns = [
    # ... other patterns
    path('accounting/', include('accounting.urls.invoice_urls')),
]
```

### 5. Install Dependencies

Ensure required packages are installed:

```bash
pip install qrcode[pil] requests pillow
```

## Usage

### Creating a Sales Invoice

1. **Navigate to Invoice List**
   ```
   /accounting/invoices/
   ```

2. **Click "New Invoice"**
   - Fill in customer details
   - Add invoice lines (description, quantity, price)
   - Set payment terms and due date

3. **Save as Draft**
   - Invoice is saved but not posted
   - Can be edited before posting

### Posting and IRD Submission

#### Option 1: Post and Auto-Submit
1. Check "Auto-submit to IRD" checkbox
2. Click "Post Invoice"
3. System will:
   - Create journal entries
   - Submit to IRD
   - Generate QR code

#### Option 2: Manual IRD Submission
1. Post invoice first
2. Click "Submit to IRD" button
3. Wait for confirmation
4. QR code will be generated upon success

### Viewing Invoice Details

```
/accounting/invoices/<invoice_id>/
```

Features:
- View complete invoice details
- See IRD sync status
- Display QR code (if synced)
- Access action buttons (edit, print, cancel)

### Printing Invoices

```
/accounting/invoices/<invoice_id>/print/
```

Features:
- Professional invoice layout
- QR code display (if IRD-synced)
- Reprint watermark for audit compliance
- Auto-track reprint count

### Batch IRD Submission

1. Go to invoice list
2. Select multiple invoices using checkboxes
3. Click "Batch Submit to IRD"
4. System processes all selected invoices
5. Shows success/failure summary

### Cancelling Invoice in IRD

1. Open invoice details
2. Click "Cancel in IRD" (only for synced invoices)
3. Enter cancellation reason (required)
4. Confirm cancellation
5. System updates IRD and local status

### IRD Dashboard

```
/accounting/ird-dashboard/
```

Features:
- Overall sync statistics
- Success rate visualization
- Recent submissions list
- Failed submissions with retry option
- Pending invoices count

## API Endpoints

### AJAX Endpoints

#### Submit Invoice to IRD
```javascript
POST /accounting/invoices/<invoice_id>/submit-ird/
Headers: X-Requested-With: XMLHttpRequest

Response:
{
  "success": true,
  "ird_ack_id": "ABC123456",
  "ird_signature": "...",
  "qr_data": "...",
  "message": "Invoice submitted successfully"
}
```

#### Get QR Code Image
```
GET /accounting/invoices/<invoice_id>/qr-code/
Returns: PNG image
```

#### Batch Submission
```javascript
POST /accounting/invoices/batch-submit-ird/
Data: invoice_ids[]=1&invoice_ids[]=2

Response:
{
  "success": [...],
  "failed": [...],
  "total": 2
}
```

#### Get Customer Details
```javascript
GET /accounting/ajax/customer/<customer_id>/

Response:
{
  "success": true,
  "customer": {
    "id": 1,
    "name": "Customer Name",
    "tax_id": "123456789",
    "address": "...",
    "payment_term_id": 1
  }
}
```

## IRD Service Class

### Usage Example

```python
from accounting.services.ird_ebilling import IRDEBillingService
from accounting.models import SalesInvoice, Organization

# Initialize service
organization = Organization.objects.get(id=1)
ird_service = IRDEBillingService(organization)

# Submit invoice
invoice = SalesInvoice.objects.get(id=1)
result = ird_service.submit_invoice(invoice)

if result['success']:
    print(f"Success! Ack ID: {result['ack_id']}")
    print(f"QR Data: {result['qr_data']}")
else:
    print(f"Failed: {result['error']}")

# Generate QR code image
qr_image = ird_service.generate_qr_code_image(result['qr_data'])

# Cancel invoice
result = ird_service.cancel_invoice(invoice, "Duplicate entry")

# Track reprint
result = ird_service.print_invoice(invoice)
```

## Invoice Workflow

```
1. Create Invoice (Draft)
   ↓
2. Add Line Items
   ↓
3. Review & Validate
   ↓
4. Post Invoice
   ↓
5. Submit to IRD (Auto/Manual)
   ↓
6. IRD Processing
   ↓
7. Success: Get Ack ID + Signature + QR
   ↓
8. Print Invoice with QR Code
   ↓
9. Track Reprints
```

## IRD Status States

| Status | Description | Actions Available |
|--------|-------------|------------------|
| `null` | Not submitted | Submit to IRD |
| `pending` | Queued for submission | Wait or retry |
| `synced` | Successfully submitted | Print, Cancel |
| `failed` | Submission failed | Retry, Edit |
| `cancelled` | Cancelled in IRD | View only |

## Security & Compliance

### Data Protection
- IRD credentials stored in environment variables
- API responses encrypted in database
- SSL/TLS required for API calls

### Audit Trail
- All submissions logged with timestamp
- User tracking for create/update actions
- Reprint count monitored
- 7-year retention as per Nepal tax law

### Invoice Locking
- IRD-synced invoices cannot be edited
- Cancellation requires reason (min 10 chars)
- Cancellation is permanent and reported to IRD

## Error Handling

### Common Errors

#### 1. IRD API Timeout
```
Error: IRD API timeout - please try again
Solution: Retry submission
```

#### 2. Invalid PAN
```
Error: Customer PAN validation failed
Solution: Verify and update customer PAN
```

#### 3. Duplicate Submission
```
Error: Invoice already submitted to IRD
Solution: Check invoice status
```

#### 4. Network Error
```
Error: Unable to connect to IRD server
Solution: Check internet connection, retry later
```

### Retry Mechanism

Failed submissions can be retried:
1. From invoice detail page
2. From IRD dashboard
3. Automatically (if enabled in settings)

## Performance Optimization

### Async Submission (Optional)

Enable Celery for background processing:

```python
# settings.py
IRD_USE_ASYNC_SUBMISSION = True

# celery.py
from celery import Celery
app = Celery('erp')

@app.task
def submit_invoice_to_ird_async(invoice_id):
    # ... implementation
```

### Batch Processing

For bulk submissions:
- Use batch endpoint
- Process in chunks of 50
- Implement rate limiting

## Testing

### Unit Tests

```bash
python manage.py test accounting.tests.test_ird_service
```

### Integration Tests

```bash
# Use IRD testing environment
IRD_TESTING_MODE=true python manage.py test
```

### Mock API (Development)

```python
# settings.py
IRD_MOCK_API = True  # Uses mock responses
```

## Troubleshooting

### Issue: QR Code Not Showing
**Solution:** Ensure invoice is IRD-synced and has `ird_ack_id`

### Issue: Cannot Edit Invoice
**Solution:** Check if invoice is posted or IRD-synced (locked)

### Issue: Batch Submit Fails
**Solution:** Check individual invoice status, ensure all are posted

### Issue: IRD Credentials Invalid
**Solution:** Verify credentials in environment variables

## Fiscal Year Conversion

Nepal uses Bikram Sambat calendar:

```python
# Automatic conversion in IRDConfig
fiscal_year = IRDConfig.get_fiscal_year_code(invoice_date)
# Returns: "2080/81" for BS year 2080-2081
```

## Support & Documentation

- **IRD Official Documentation:** https://ird.gov.np
- **Technical Support:** tech-support@example.com
- **User Guide:** See `/docs/user_guide.pdf`

## License

Proprietary - Himalytix ERP System

## Version History

- **v1.0.0** (2025-11-28): Initial release with complete IRD integration
  - Real-time invoice submission
  - QR code generation
  - Batch processing
  - Comprehensive audit trail

---

**Note:** Always test with IRD testing environment before going live. Ensure proper backup procedures are in place for production deployment.
