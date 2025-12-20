import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounting.models import VoucherModeConfig

print("\n" + "="*80)
print("VOUCHER MODE CONFIG VERIFICATION")
print("="*80)

configs = VoucherModeConfig.objects.filter(organization_id=1).order_by('code')

print(f"\nTotal vouchers configured: {configs.count()}/17\n")

issues = []
for i, config in enumerate(configs, 1):
    # Check critical fields
    has_ui_schema = bool(config.schema_definition)
    has_journal_type = bool(config.journal_type_id)
    
    status_icon = "OK" if (has_ui_schema and has_journal_type) else "!!"
    
    print(f"{i:2}. {status_icon} {config.code:20} | {config.name[:40]:40} | Schema: {'YES' if has_ui_schema else 'NO ':3} | JType: {config.journal_type_id or 'N/A'}")
    
    if not has_ui_schema:
        issues.append(f"{config.code}: Missing schema_definition")
    if not has_journal_type:
        issues.append(f"{config.code}: Missing journal_type_id")

print("\n" + "="*80)
if issues:
    print("ISSUES FOUND:")
    for issue in issues:
        print(f"  - {issue}")
else:
    print("ALL VOUCHERS PROPERLY CONFIGURED!")
print("="*80)

# Test form generation for a sample voucher
print("\n" + "="*80)
print("TESTING FORM GENERATION")
print("="*80)

try:
    from accounting.forms_factory import VoucherFormFactory
    from usermanagement.models import Organization
    
    org = Organization.objects.get(pk=1)
    
    # Test 3 different vouchers
    test_codes = ['VM-SI', 'VM-PI', 'VM13']
    
    for code in test_codes:
        try:
            config = VoucherModeConfig.objects.get(code=code, organization=org)
            form_class = VoucherFormFactory.get_generic_voucher_form(config, org)
            print(f"OK {code:15} - Form generated successfully ({len(form_class.base_fields)} fields)")
        except VoucherModeConfig.DoesNotExist:
            print(f"!! {code:15} - Config not found")
        except Exception as e:
            print(f"XX {code:15} - Error: {str(e)[:60]}")
    
    print("="*80)
    
except Exception as e:
    print(f"XX Form generation test failed: {e}")
    import traceback
    traceback.print_exc()
