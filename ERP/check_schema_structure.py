import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounting.models import VoucherModeConfig

# Check one voucher's schema structure
config = VoucherModeConfig.objects.filter(code='VM-SI').first()
if config:
    print(f"Voucher: {config.code} - {config.name}")
    print("\nui_schema structure:")
    print(json.dumps(config.ui_schema, indent=2))
else:
    print("VM-SI not found")
