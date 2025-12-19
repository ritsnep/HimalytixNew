#!/usr/bin/env python
"""Check database tables"""
import os
import sys
import django
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection

cursor = connection.cursor()
cursor.execute("""
    SELECT tablename 
    FROM pg_tables 
    WHERE schemaname='public' AND tablename LIKE '%voucher%'
    ORDER BY tablename
""")

print("\nVoucher-related tables in database:")
print("="*50)
for row in cursor.fetchall():
    print(f"  - {row[0]}")
print()
