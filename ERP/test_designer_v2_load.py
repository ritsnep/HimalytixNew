import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard.settings')
django.setup()

from accounting.models import VoucherModeConfig
from forms_designer.utils import get_active_schema
import json

config = VoucherModeConfig.objects.get(config_id=1)
schema = get_active_schema(config)

print("=== Schema from get_active_schema ===")
print(f"Type: {type(schema)}")
print(f"Keys: {schema.keys() if isinstance(schema, dict) else 'N/A'}")
print(f"\nHeader type: {type(schema.get('header')) if isinstance(schema, dict) else 'N/A'}")
print(f"Lines type: {type(schema.get('lines')) if isinstance(schema, dict) else 'N/A'}")

if isinstance(schema, dict):
    if isinstance(schema.get('header'), dict):
        print(f"\n❌ Header is DICT with {len(schema['header'])} keys:")
        print(f"   Keys: {list(schema['header'].keys())}")
    elif isinstance(schema.get('header'), list):
        print(f"\n✓ Header is LIST with {len(schema['header'])} items")
    
    if isinstance(schema.get('lines'), dict):
        print(f"\n❌ Lines is DICT with {len(schema['lines'])} keys:")
        print(f"   Keys: {list(schema['lines'].keys())}")
    elif isinstance(schema.get('lines'), list):
        print(f"\n✓ Lines is LIST with {len(schema['lines'])} items")

print("\n=== After conversion (simulating designer_v2 view) ===")

# Simulate the conversion in designer_v2
for section in ['header', 'lines']:
    if isinstance(schema[section], dict):
        schema[section] = [
            {**field, 'name': name} for name, field in schema[section].items()
        ]
        print(f"Converted {section} from dict to list")

print(f"\nAfter conversion:")
print(f"Header type: {type(schema.get('header'))}, length: {len(schema['header'])}")
print(f"Lines type: {type(schema.get('lines'))}, length: {len(schema['lines'])}")

if schema['header']:
    print(f"\nSample header field: {json.dumps(schema['header'][0], indent=2)}")
