import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounting.models import VoucherModeConfig, Organization
from accounting.forms_factory import VoucherFormFactory

# Test form generation with debug
org = Organization.objects.first()
config = VoucherModeConfig.objects.filter(code='VM-SI').first()

if config and org:
    print(f"Testing: {config.code}")
    resolved = config.resolve_ui_schema()
    print(f"\nResolved schema keys: {resolved.keys()}")
    
    # Manually trace schema processing
    schema = resolved
    
    # Step 1: Unwrap sections
    if 'sections' in schema:
        schema = schema['sections']
        print(f"After unwrapping sections: {schema.keys()}")
    
    # Step 2: Get header
    if 'header' in schema:
        schema = schema['header']
        print(f"After getting header: {schema.keys()}")
    
    # Step 3: Get fields
    if 'fields' in schema and isinstance(schema.get('fields'), dict):
        order = schema.get('__order__')
        schema = schema['fields']
        print(f"After getting fields: {schema.keys()}")
        print(f"Order preserved: {order}")
    
    # Check autofocus
    print(f"\nField configs:")
    for name, cfg in schema.items():
        if name != '__order__':
            autofocus = cfg.get('autofocus', 'NOT SET')
            print(f"  {name}: autofocus={autofocus}")
