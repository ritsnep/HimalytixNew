import os
import django
import copy
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounting.models import VoucherModeConfig, Organization
from datetime import date

config = VoucherModeConfig.objects.get(code='VM-SI')
org = Organization.objects.first()

print("BEFORE augmentation:")
print(json.dumps(config.ui_schema['sections']['header']['fields']['voucher_date'], indent=2))

# Simulate augmentation
schema_copy = copy.deepcopy(config.ui_schema)
sections = schema_copy['sections']
header = sections['header']
header_fields = header['fields']

# This is what ensure_field does for voucher_date
if 'voucher_date' not in header_fields:
    header_fields['voucher_date'] = {
        'label': 'Date',
        'type': 'date',
        'required': False,
        'order_no': 0,
        'kwargs': {'widget': {'attrs': {'value': date.today().isoformat()}}}
    }
    print("\nField was added by augmentation (field didn't exist)")
else:
    print("\nField already exists, NOT modified by augmentation")

print("\nAFTER augmentation:")
print(json.dumps(header_fields['voucher_date'], indent=2))
