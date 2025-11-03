import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard.settings')
django.setup()

from forms_designer.models import VoucherSchema, VoucherSchemaStatus
from accounting.models import VoucherModeConfig

config = VoucherModeConfig.objects.get(config_id=1)
print(f'Config ID 1: {config}')
print(f'Organization: {config.organization}')

schemas = VoucherSchema.objects.filter(voucher_mode_config=config).order_by('-version')
print(f'\nTotal schemas for config 1: {schemas.count()}')

for s in schemas:
    header_count = len(s.schema.get('header', [])) if isinstance(s.schema.get('header'), list) else len(s.schema.get('header', {}).keys())
    lines_count = len(s.schema.get('lines', [])) if isinstance(s.schema.get('lines'), list) else len(s.schema.get('lines', {}).keys())
    print(f'\nv{s.version}:')
    print(f'  Status: {s.status}')
    print(f'  Is Active: {s.is_active}')
    print(f'  Header fields: {header_count}')
    print(f'  Lines fields: {lines_count}')
    
    if s.is_active or s.status == VoucherSchemaStatus.PUBLISHED:
        print(f'  Header structure: {type(s.schema.get("header"))}')
        print(f'  Lines structure: {type(s.schema.get("lines"))}')
        if header_count > 0:
            print(f'  Sample header data: {json.dumps(s.schema.get("header")[:2] if isinstance(s.schema.get("header"), list) else dict(list(s.schema.get("header", {}).items())[:2]), indent=2)}')
