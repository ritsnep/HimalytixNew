import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounting.models import VoucherModeConfig, Organization
from accounting.forms_factory import VoucherFormFactory

# Test form generation with autofocus
org = Organization.objects.first()
config = VoucherModeConfig.objects.filter(code='VM-SI').first()

if config and org:
    print(f"Testing: {config.code} - {config.name}\n")
    
    # Generate form
    form_class = VoucherFormFactory.get_generic_voucher_form(config, org)
    form = form_class()
    
    print(f"Form has {len(form.fields)} fields\n")
    
    for field_name, field in form.fields.items():
        autofocus = field.widget.attrs.get('autofocus', False)
        print(f"{field_name:20} | autofocus={autofocus} | widget={field.widget.__class__.__name__}")
