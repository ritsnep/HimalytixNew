
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard.settings")
django.setup()

from django.db import connection

def diagnose():
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_user")
        print(f"Current User: {cursor.fetchone()[0]}")
        
        cursor.execute("SHOW search_path")
        print(f"Search Path: {cursor.fetchone()[0]}")

        cursor.execute("SELECT schema_name FROM information_schema.schemata")
        schemas = [row[0] for row in cursor.fetchall()]
        print(f"All Schemas: {schemas}")

        for schema in schemas:
            cursor.execute(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = %s AND table_name = 'currency')",
                [schema]
            )
            has_table = cursor.fetchone()[0]
            
            if has_table:
                cursor.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = 'currency' AND column_name = 'isdefault'",
                    [schema]
                )
                col = cursor.fetchone()
                has_col = bool(col)
                print(f"Schema '{schema}': Table=YES, Column 'isdefault'={has_col}")
            else:
                pass # print(f"Schema '{schema}': Table=NO")

if __name__ == "__main__":
    diagnose()
