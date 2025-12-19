import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection

cursor = connection.cursor()

# Add the is_balanced column
print("\nAdding is_balanced column...")
try:
    cursor.execute("""
        ALTER TABLE accounting_journal 
        ADD COLUMN is_balanced BOOLEAN NOT NULL DEFAULT TRUE
    """)
    connection.commit()
    print("OK Column added successfully")
except Exception as e:
    print(f"ERROR adding column: {e}")
    connection.rollback()

# Create index
print("\nCreating index on is_balanced...")
try:
    cursor.execute("""
        CREATE INDEX accounting_journal_is_balanced_idx 
        ON accounting_journal(is_balanced)
    """)
    connection.commit()
    print("OK Index created successfully")
except Exception as e:
    print(f"ERROR creating index: {e}")
    connection.rollback()

# Verify
cursor.execute("""
    SELECT column_name, data_type, is_nullable, column_default
    FROM information_schema.columns 
    WHERE table_schema = 'public'
    AND table_name='accounting_journal' 
    AND column_name='is_balanced'
""")

result = cursor.fetchone()
if result:
    print(f"\nOK is_balanced column verified:")
    print(f"  column_name: {result[0]}")
    print(f"  data_type: {result[1]}")
    print(f"  is_nullable: {result[2]}")
    print(f"  column_default: {result[3]}")
else:
    print("\nERROR is_balanced column NOT FOUND")
