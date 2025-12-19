import os
import django
from django.db import connection

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard.settings')
django.setup()

with connection.cursor() as cursor:
    try:
        cursor.execute("SELECT count(*) FROM voucher_configuration")
        count = cursor.fetchone()[0]
        print(f"Found {count} rows in voucher_configuration")
    except Exception as e:
        print(f"Error: {e}")
