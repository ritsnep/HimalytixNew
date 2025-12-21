
import os
import django
import json
import sys

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard.settings")
django.setup()

from accounting.models import VoucherModeConfig

try:
    config_data = VoucherModeConfig.objects.filter(code='VM-PI').values('schema_definition').first()
    if not config_data:
        print("Config VM-PI NOT FOUND")
    else:
        schema = config_data['schema_definition']
        try:
            data = json.loads(schema)
            header_fields = data.get('header', [])
            
            # If it's a dict (old schema style) or list (new schema style)
            if isinstance(header_fields, dict):
                 # Convert dict to keys for checking
                 keys = list(header_fields.keys())
            elif isinstance(header_fields, list):
                 keys = [f.get('key') for f in header_fields]
            
            with open('dupes_result.txt', 'w') as f:
                f.write(f"Header Keys ({len(keys)}): {keys}\n")
                if dupes:
                    f.write(f"FAILURE: Duplicate header keys found: {dupes}\n")
                else:
                    f.write("SUCCESS: No duplicate header keys found.\n")

        except Exception as e:
            with open('dupes_result.txt', 'w') as f:
                f.write(f"Schema Parse Error: {e}\n")

except Exception as e:
    with open('dupes_result.txt', 'w') as f:
        f.write(f"Error: {e}\n")
