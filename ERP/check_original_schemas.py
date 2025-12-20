import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounting.models import VoucherModeConfig

# Check some original vouchers
for code in ['VM001', 'VM01', 'VM02']:
    config = VoucherModeConfig.objects.filter(code=code).first()
    if config:
        print(f"\n{'='*60}")
        print(f"Voucher: {config.code} - {config.name}")
        print(f"{'='*60}")
        print(json.dumps(config.resolve_ui_schema(), indent=2)[:500])
        print("...")
