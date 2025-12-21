
import os
import django
import sys

# Ensure project root is in path
sys.path.append(os.getcwd())

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard.settings")
django.setup()

from django.db import connection

def checks():
    print("Connecting...")
    with connection.cursor() as cursor:
        # Check DB name again
        cursor.execute("SELECT current_database()")
        print("DB:", cursor.fetchone()[0])
        
        # Check explicit public schema select
        print("Attempting SELECT from public.currency...")
        try:
            cursor.execute('SELECT "isdefault" FROM "public"."currency" LIMIT 1')
            print("SELECT public.currency Success:", cursor.fetchone())
        except Exception as e:
            print("SELECT public.currency Failed:", e)
            
        # Check default search path select
        print("Attempting SELECT from currency (default path)...")
        try:
            # Re-open transaction/cursor if needed? No, auto-recover?
            # Postgres needs rollback if failed.
            pass 
        except:
            pass

        # We need fresh cursor/transaction if previous failed
    
    # New connection/transaction for second try
    connection.close()
    with connection.cursor() as cursor:
        try:
            cursor.execute('SELECT "isdefault" FROM "currency" LIMIT 1')
            print("SELECT currency Success:", cursor.fetchone())
        except Exception as e:
            print("SELECT currency Failed:", e)

if __name__ == "__main__":
    checks()
