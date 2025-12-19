import os
import django
from django.db import connection

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard.settings')
django.setup()

with connection.cursor() as cursor:
    try:
        cursor.execute("DROP TABLE IF EXISTS voucher_configuration CASCADE")
        print("Dropped voucher_configuration if it existed")
    except Exception as e:
        print(f"Error: {e}")
