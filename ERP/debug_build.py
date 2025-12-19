import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounting.models import VoucherModeConfig, Organization
from accounting.forms_factory import VoucherFormFactory

# Add debug output to see what's happening
import accounting.forms_factory as ff

original_build_field = ff.VoucherFormFactory._build_field

def debug_build_field(self, field_name, config):
    result = original_build_field(field_name, config)
    if field_name == 'voucher_date':
        print(f"\nDEBUG _build_field for voucher_date:")
        print(f"  config.get('autofocus'): {config.get('autofocus')}")
        if result and hasattr(result, 'widget'):
            print(f"  widget attrs: {result.widget.attrs}")
    return result

ff.VoucherFormFactory._build_field = debug_build_field

org = Organization.objects.first()
config = VoucherModeConfig.objects.get(code='VM-SI')

form_class = VoucherFormFactory.get_generic_voucher_form(config, org)
form = form_class()

print(f"\n\nFinal form field autofocus:")
for name, field in form.fields.items():
    if name == 'voucher_date':
        print(f"  {name}: {field.widget.attrs.get('autofocus', 'NOT SET')}")
