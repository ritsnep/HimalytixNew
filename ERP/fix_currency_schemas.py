
import os
import django
from dotenv import load_dotenv

load_dotenv()

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard.settings")
django.setup()

from django.db import connection
from django import db

# Close any existing connections to avoid transaction aborted state
db.connections.close_all()

def fix_schemas():
    with connection.cursor() as cursor:
        # Get all schema names
        cursor.execute("SELECT schema_name FROM information_schema.schemata")
        schemas = [row[0] for row in cursor.fetchall()]

        print(f"Found {len(schemas)} schemas: {schemas}")

        for schema in schemas:
            if schema in ('information_schema', 'pg_catalog', 'pg_toast'):
                continue
            
            # Check if currency table exists in this schema
            cursor.execute(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = %s AND table_name = 'currency')",
                [schema]
            )
            table_exists = cursor.fetchone()[0]
            
            if not table_exists:
                continue

            print(f"Checking schema '{schema}'...")
            
            # Check if column exists
            cursor.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = 'currency' AND column_name = 'isdefault'",
                [schema]
            )
            col_exists = cursor.fetchone()
            
            if col_exists:
                print(f"  - Schema '{schema}': Column 'isdefault' already exists.")
            else:
                print(f"  - Schema '{schema}': Adding column 'isdefault'...")
                try:
                    # Use quote_ident style manually for safety
                    safe_schema = schema.replace('"', '""')
                    sql = f'ALTER TABLE "{safe_schema}"."currency" ADD COLUMN isdefault BOOLEAN DEFAULT FALSE'
                    cursor.execute(sql)
                    print(f"  - Schema '{schema}': SUCCESS")
                except Exception as e:
                    print(f"  - Schema '{schema}': FAILED - {e}")

if __name__ == "__main__":
    fix_schemas()
