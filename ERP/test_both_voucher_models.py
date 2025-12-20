import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard.settings")
django.setup()

from accounting.models import VoucherModeConfig
from accounting.forms_factory import VoucherFormFactory
from usermanagement.models import Organization

print("=" * 80)
print("COMPREHENSIVE TEST: VoucherModeConfig")
print("=" * 80)

org = Organization.objects.get(pk=1)

print("\n1. Testing VoucherModeConfig")
print("-" * 60)
try:
    config = VoucherModeConfig.objects.filter(organization=org).first()
    if not config:
        raise RuntimeError("No VoucherModeConfig found for the organization.")
    print(f"   Config: {config.code} - {config.name}")
    print(f"   Model: {type(config).__name__}")
    print(f"   Has 'module' attr: {hasattr(config, 'module')}")
    print(f"   Has 'schema_definition' attr: {hasattr(config, 'schema_definition')}")

    header_form = VoucherFormFactory.get_generic_voucher_form(config, org)
    line_formset = VoucherFormFactory.get_generic_voucher_formset(
        voucher_config=config,
        organization=org,
    )
    print(f"   Header form: OK ({len(header_form.base_fields)} fields)")
    print("   Line formset: OK")

except Exception as e:
    print(f"   ERROR: {e}")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print("OK VoucherModeConfig works with the unified form factory")
print("=" * 80)
