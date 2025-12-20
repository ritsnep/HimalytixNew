import os
import django
import json
from dotenv import load_dotenv
load_dotenv()

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard.settings')
django.setup()

from accounting.models import VoucherModeConfig

config_code = 'sales-invoice'
config = VoucherModeConfig.objects.filter(code=config_code).first()
if config:
    print(json.dumps(config.resolve_ui_schema(), indent=2))
else:
    print(f"Config not found: {config_code}")
