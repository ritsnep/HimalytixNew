import os
import django
import json
from dotenv import load_dotenv
load_dotenv()

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard.settings')
django.setup()

from accounting.models import VoucherConfiguration

config = VoucherConfiguration.objects.filter(code='VM08').first()
if config:
    print(json.dumps(config.ui_schema, indent=2))
else:
    print("Config not found")
