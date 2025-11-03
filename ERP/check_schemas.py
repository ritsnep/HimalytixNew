import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard.settings')
django.setup()

from forms_designer.models import VoucherSchema
from accounting.models import VoucherModeConfig

config = VoucherModeConfig.objects.first()
print(f'Config: {config}')

schemas = VoucherSchema.objects.filter(voucher_mode_config=config).order_by('-version')
print(f'Total schemas: {schemas.count()}')

for s in schemas:
    header_count = len(s.schema.get('header', [])) if isinstance(s.schema.get('header'), list) else len(s.schema.get('header', {}).keys())
    lines_count = len(s.schema.get('lines', [])) if isinstance(s.schema.get('lines'), list) else len(s.schema.get('lines', {}).keys())
    print(f'  v{s.version}: status={s.status}, is_active={s.is_active}, header={header_count} fields, lines={lines_count} fields')
