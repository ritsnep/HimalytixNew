from accounting.models import SalesInvoice
from accounting.services.ird_ebilling import IRDEBillingService

invoice_id = 1
invoice = SalesInvoice.objects.filter(invoice_id=invoice_id).first()
if not invoice:
    raise SystemExit('Invoice not found')

service = IRDEBillingService(invoice.organization)
# Create dummy qr_data without IRD signature
qr_data = f"DUMMY,{invoice.invoice_number},{invoice.invoice_date.strftime('%Y-%m-%d')},{invoice.total},DUMMY_SIG"
img_buf = service.generate_qr_code_image(qr_data)
out = f'scripts/qr_local_invoice_{invoice_id}.png'
with open(out, 'wb') as f:
    f.write(img_buf.getvalue())
print('Saved local QR to', out)
