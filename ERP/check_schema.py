#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard.settings')
django.setup()

from django.db import connection
from accounting.models import AuditLog

# Test if we can query the table
print(f"AuditLog model fields:")
for field in AuditLog._meta.fields:
    print(f"  {field.name}: {field.get_internal_type()}")

# Try to fetch one record
try:
    audit = AuditLog.objects.first()
    if audit:
        print(f"\nFirst audit log entry:")
        print(f"  ID: {audit.id}")
        print(f"  Organization: {audit.organization}")
        print(f"  User: {audit.user}")
        print(f"  Action: {audit.action}")
    else:
        print("No audit log entries found.")
except Exception as e:
    print(f"Error querying table: {e}")
