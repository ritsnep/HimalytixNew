import os, django, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounting.models import VoucherModeConfig, Organization
from accounting.forms_factory import VoucherFormFactory

config = VoucherModeConfig.objects.get(code='VM-SI')
org = Organization.objects.first()

# Check what the augmented schema looks like
form_cls = VoucherFormFactory.get_generic_voucher_form(config, org)
form = form_cls()

print("Status field configuration:")
status_field = form.fields.get('status')
if status_field:
    print(f"  Required: {status_field.required}")
    print(f"  Initial: {status_field.initial}")
    print(f"  Disabled: {status_field.disabled}")
    print(f"  Widget: {status_field.widget}")
    print(f"  Widget attrs: {status_field.widget.attrs}")
