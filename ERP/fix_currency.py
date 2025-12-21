
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard.settings")
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    try:
        cursor.execute("ALTER TABLE currency ADD COLUMN isdefault BOOLEAN DEFAULT FALSE;")
        print("Column 'isdefault' added successfully.")
    except Exception as e:
        if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
            print("Column 'isdefault' already exists.")
        else:
            raise
