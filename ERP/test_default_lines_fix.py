import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounting.models import VoucherModeConfig
from accounting.forms_factory import VoucherFormFactory
from usermanagement.models import Organization

print("="*80)
print("TESTING FORM GENERATION WITH FIXED default_lines ATTRIBUTE")
print("="*80)

try:
    org = Organization.objects.get(pk=1)
    config = VoucherModeConfig.objects.get(code='sales-invoice-vm-si', organization=org)
    
    print(f"\nTesting voucher: {config.code} - {config.name}")
    print(f"Has default_lines attribute: {hasattr(config, 'default_lines')}")
    
    # Test header form generation
    print("\n1. Generating header form...")
    try:
        header_form = VoucherFormFactory.get_generic_voucher_form(config, org)
        print(f"   OK Header form generated with {len(header_form.base_fields)} fields")
    except Exception as e:
        print(f"   ERROR: {e}")
        raise
    
    # Test formset generation
    print("\n2. Generating line formset...")
    try:
        line_formset = VoucherFormFactory.get_generic_voucher_formset(
            voucher_config=config,
            organization=org
        )
        print(f"   OK Line formset generated successfully")
    except Exception as e:
        print(f"   ERROR: {e}")
        raise
    
    print("\n" + "="*80)
    print("SUCCESS! Both header form and line formset generated without errors")
    print("="*80)
    
except VoucherModeConfig.DoesNotExist:
    print("ERROR: sales-invoice-vm-si config not found")
except Organization.DoesNotExist:
    print("ERROR: Organization with ID 1 not found")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
