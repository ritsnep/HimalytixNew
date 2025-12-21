
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard.settings")
django.setup()

from django.db import connection

# Close stale connections
from django import db
db.connections.close_all()

from accounting.models import Currency, FiscalYear, AccountingPeriod
from usermanagement.models import Organization
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model

User = get_user_model()
today = timezone.now().date()

print("Step 1: Get/Create Currency...")
try:
    default_currency, created = Currency.objects.get_or_create(
        currency_code="USD",
        defaults={"currency_name": "US Dollar", "symbol": "$"},
    )
    print(f"  Currency: {default_currency}, created={created}")
except Exception as e:
    print(f"  ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\nStep 2: Get/Create Organization...")
try:
    org, created = Organization.objects.get_or_create(
        name="Demo Org",
        defaults={
            "code": "DEMO-001",
            "type": "company",
            "base_currency_code": default_currency,
            "is_active": True,
        },
    )
    print(f"  Organization: {org}, created={created}")
except Exception as e:
    print(f"  ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\nStep 3: Get/Create FiscalYear...")
try:
    fy, created = FiscalYear.objects.get_or_create(
        organization=org,
        code=f"FY{today.year}",
        defaults={
            "name": f"Fiscal Year {today.year}",
            "start_date": today.replace(month=1, day=1),
            "end_date": today.replace(month=12, day=31),
            "is_current": True,
        },
    )
    print(f"  FiscalYear: {fy}, created={created}")
except Exception as e:
    print(f"  ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\nStep 4: Get/Create AccountingPeriod...")
try:
    period, created = AccountingPeriod.objects.get_or_create(
        fiscal_year=fy,
        period_number=today.month,
        name=f"{today.year}-{today.month:02d}",
        defaults={
            "start_date": today.replace(day=1),
            "end_date": (today.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1),
            "status": "open",
        },
    )
    print(f"  AccountingPeriod: {period}, created={created}")
except Exception as e:
    print(f"  ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\nDone!")
