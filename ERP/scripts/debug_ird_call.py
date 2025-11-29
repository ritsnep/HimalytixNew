import json
from django.conf import settings
from accounting.services.ird_ebilling import IRDEBillingService
from accounting.models import SalesInvoice

OUT_DIR = 'scripts'

print('Reading IRD settings from Django settings...')
ird_url = getattr(settings, 'IRD_API_URL', None)
ird_user = getattr(settings, 'IRD_USERNAME', None)
ird_pass = getattr(settings, 'IRD_PASSWORD', None)
ird_pan = getattr(settings, 'IRD_SELLER_PAN', None)
print('IRD_API_URL =', ird_url)
print('IRD_USERNAME =', bool(ird_user))
print('IRD_PASSWORD =', bool(ird_pass))
print('IRD_SELLER_PAN =', ird_pan)

invoice_id = 1
invoice = SalesInvoice.objects.filter(invoice_id=invoice_id).first()
if not invoice:
    raise SystemExit(f'Invoice {invoice_id} not found')

service = IRDEBillingService(invoice.organization)
payload = service._prepare_invoice_payload(invoice)

# Save payload
with open(f'{OUT_DIR}/ird_payload_invoice_{invoice_id}.json', 'w', encoding='utf-8') as f:
    json.dump(payload, f, indent=2, ensure_ascii=False)
print('Saved payload to', f'{OUT_DIR}/ird_payload_invoice_{invoice_id}.json')

# Make the call and capture response (do not fail on exceptions)
import requests

endpoint = service.config.API_BASE_URL + '/invoice/submit'
print('Posting to', endpoint)
try:
    resp = requests.post(endpoint, json=payload, timeout=30)
    # Save raw response
    try:
        resp_json = resp.json()
    except Exception:
        resp_json = None

    with open(f'{OUT_DIR}/ird_response_invoice_{invoice_id}.txt', 'w', encoding='utf-8') as f:
        f.write(f'Status Code: {resp.status_code}\n')
        f.write('Headers:\n')
        for k, v in resp.headers.items():
            f.write(f'{k}: {v}\n')
        f.write('\nBody:\n')
        f.write(resp.text)

    if resp_json is not None:
        with open(f'{OUT_DIR}/ird_response_invoice_{invoice_id}.json', 'w', encoding='utf-8') as f:
            json.dump(resp_json, f, indent=2, ensure_ascii=False)

    print('Saved response to', f'{OUT_DIR}/ird_response_invoice_{invoice_id}.txt')
    if resp_json is not None:
        print('Saved parsed JSON to', f'{OUT_DIR}/ird_response_invoice_{invoice_id}.json')
    print('HTTP status:', resp.status_code)

except requests.exceptions.RequestException as e:
    # Save exception info
    with open(f'{OUT_DIR}/ird_response_invoice_{invoice_id}_error.txt', 'w', encoding='utf-8') as f:
        f.write(str(e))
    print('Request failed:', e)
    print('Saved exception to', f'{OUT_DIR}/ird_response_invoice_{invoice_id}_error.txt')

print('Done')
