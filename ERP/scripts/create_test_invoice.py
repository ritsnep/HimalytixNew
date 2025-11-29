from django.utils import timezone
from datetime import timedelta, date

from accounting.models import (
    SalesInvoice, SalesInvoiceLine, Customer, ChartOfAccount, Currency, Organization
)
from accounting.services.ird_ebilling import IRDEBillingService

# Find or create organization
org = Organization.objects.first()
if not org:
    org = Organization.objects.create(name='Test Org', code='TEST', type='test')
    print('Created Organization:', org)
else:
    print('Using Organization:', org)

# Currency
currency = Currency.objects.first()
if not currency:
    currency = Currency.objects.create(currency_code='NPR', currency_name='Nepalese Rupee', symbol='Rs')
    print('Created Currency:', currency)
else:
    print('Using Currency:', currency)

# Revenue account
rev_account = ChartOfAccount.objects.filter(organization=org).first()
if not rev_account:
    rev_account = ChartOfAccount.objects.first()
if not rev_account:
    print('No ChartOfAccount available. Cannot create invoice line. Exiting.')
    raise SystemExit(1)
print('Using revenue account:', rev_account)

# Find or create customer
customer = Customer.objects.filter(organization=org).first()
if not customer:
    # Ensure we have an AR account for the customer
    ar_account = rev_account or ChartOfAccount.objects.first()
    if not ar_account:
        print('No ChartOfAccount available for customer AR account. Exiting.')
        raise SystemExit(1)

    customer = Customer.objects.create(
        organization=org,
        code='CUSTTEST',
        display_name='Test Customer',
        accounts_receivable_account=ar_account,
        default_currency=currency,
        tax_id='TAXTEST001'
    )
    print('Created Customer:', customer)
else:
    print('Using Customer:', customer)

# Create invoice
today = date.today()
invoice = SalesInvoice.objects.create(
    organization=org,
    customer=customer,
    customer_display_name=customer.display_name,
    invoice_date=today,
    due_date=today + timedelta(days=7),
    currency=currency,
)

# Add a line
line = SalesInvoiceLine.objects.create(
    invoice=invoice,
    line_number=1,
    description='Test product/service',
    quantity=1,
    unit_price=1000,
    revenue_account=rev_account,
    tax_amount=0,
)

# Recompute totals
invoice.recompute_totals()
print('Created invoice:', invoice.invoice_id, invoice.invoice_number, 'Total:', invoice.total)

# Submit to IRD
ird = IRDEBillingService(org)
result = ird.submit_invoice(invoice)
print('IRD submit result:', result)

# If success, generate QR image and save
if result.get('success'):
    qr_data = result.get('qr_data') or ird._generate_qr_data(invoice, invoice.ird_last_response or {})
    img_buf = ird.generate_qr_code_image(qr_data)
    out_path = f'scripts/qr_invoice_{invoice.invoice_id}.png'
    with open(out_path, 'wb') as f:
        f.write(img_buf.getvalue())
    print('Saved QR image to', out_path)

# Call print routine
print_result = ird.print_invoice(invoice)
print('Print result:', print_result)
