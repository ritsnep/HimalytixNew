#!/usr/bin/env python
import os
import django
import sys

sys.path.insert(0, 'C:\\PythonProjects\\Himalytix\\ERP')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from accounting.views.purchase_invoice_views import purchase_invoice_new_enhanced
from accounting.models import ChartOfAccount, AccountType

print("✓ View imported successfully")

# Test AccountType model
at = AccountType.objects.first()
if at:
    print(f"✓ AccountType has name field: '{at.name}'")
else:
    print("✗ No AccountType records")
    sys.exit(1)

# Test that query works
from django.db.models import Q
org = at  # Just for testing, we'll use a real org in actual code
test_accounts = ChartOfAccount.objects.filter(
    account_type__name__in=['Cash', 'Bank']
)[:1]
print(f"✓ Query using account_type__name works correctly")

print("\n✓ All tests passed! The field name 'name' is correct.")
