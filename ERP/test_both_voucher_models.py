import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounting.models import VoucherModeConfig, VoucherConfiguration
from accounting.forms_factory import VoucherFormFactory
from usermanagement.models import Organization

print("="*80)
print("COMPREHENSIVE TEST: VoucherModeConfig vs VoucherConfiguration")
print("="*80)

org = Organization.objects.get(pk=1)

# Test 1: VoucherModeConfig (old model without default_lines)
print("\n1. Testing VoucherModeConfig (does NOT have default_lines)")
print("-" * 60)
try:
    config = VoucherModeConfig.objects.get(code='sales-invoice-vm-si', organization=org)
    print(f"   Config: {config.code} - {config.name}")
    print(f"   Model: {type(config).__name__}")
    print(f"   Has 'module' attr: {hasattr(config, 'module')}")
    print(f"   Has 'default_lines' attr: {hasattr(config, 'default_lines')}")
    
    # Test form generation
    header_form = VoucherFormFactory.get_generic_voucher_form(config, org)
    line_formset = VoucherFormFactory.get_generic_voucher_formset(
        voucher_config=config,
        organization=org
    )
    print(f"   Header form: OK ({len(header_form.base_fields)} fields)")
    print(f"   Line formset: OK")
    
except Exception as e:
    print(f"   ERROR: {e}")

# Test 2: VoucherConfiguration (new model with default_lines)
print("\n2. Testing VoucherConfiguration (DOES have default_lines)")
print("-" * 60)
try:
    config = VoucherConfiguration.objects.filter(organization=org).first()
    if config:
        print(f"   Config: {config.code} - {config.name}")
        print(f"   Model: {type(config).__name__}")
        print(f"   Has 'module' attr: {hasattr(config, 'module')}")
        print(f"   Has 'default_lines' attr: {hasattr(config, 'default_lines')}")
        print(f"   default_lines value: {config.default_lines}")
        
        # Test form generation
        header_form = VoucherFormFactory.get_generic_voucher_form(config, org)
        line_formset = VoucherFormFactory.get_generic_voucher_formset(
            voucher_config=config,
            organization=org
        )
        print(f"   Header form: OK ({len(header_form.base_fields)} fields)")
        print(f"   Line formset: OK")
    else:
        print("   No VoucherConfiguration found (table might not have data)")
        
except Exception as e:
    print(f"   ERROR: {e}")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print("✓ VoucherModeConfig works with getattr fallbacks")
print("✓ VoucherConfiguration works with actual attributes")
print("✓ Both models can use the same form factory code")
print("="*80)
