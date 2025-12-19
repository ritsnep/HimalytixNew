import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection

cursor = connection.cursor()

# First, list all current columns
cursor.execute("""
    SELECT column_name
    FROM information_schema.columns 
    WHERE table_schema = 'public'
    AND table_name='accounting_auditlog'
    ORDER BY ordinal_position
""")

print("\nCurrent columns in accounting_auditlog:")
current_columns = set()
for (col_name,) in cursor.fetchall():
    print(f"  - {col_name}")
    current_columns.add(col_name)

# Expected columns based on the model
expected_columns = {
    'id', 'timestamp', 'user_id', 'organization_id', 'action', 
    'content_type_id', 'object_id', 'changes', 'details', 'ip_address',
    'content_hash', 'previous_hash_id', 'is_immutable'
}

missing_columns = expected_columns - current_columns
if missing_columns:
    print(f"\nMissing columns: {missing_columns}")
    
    # Add missing columns
    if 'previous_hash_id' in missing_columns:
        print("\nAdding previous_hash_id column...")
        try:
            cursor.execute("""
                ALTER TABLE accounting_auditlog 
                ADD COLUMN previous_hash_id BIGINT
            """)
            # Add FK constraint to self
            cursor.execute("""
                ALTER TABLE accounting_auditlog 
                ADD CONSTRAINT accounting_auditlog_previous_hash_id_fkey 
                FOREIGN KEY (previous_hash_id) 
                REFERENCES accounting_auditlog(id)
            """)
            connection.commit()
            print("OK previous_hash_id column added")
        except Exception as e:
            print(f"ERROR adding previous_hash_id: {e}")
            connection.rollback()
    
    if 'is_immutable' in missing_columns:
        print("\nAdding is_immutable column...")
        try:
            cursor.execute("""
                ALTER TABLE accounting_auditlog 
                ADD COLUMN is_immutable BOOLEAN DEFAULT FALSE
            """)
            connection.commit()
            print("OK is_immutable column added")
        except Exception as e:
            print(f"ERROR adding is_immutable: {e}")
            connection.rollback()
else:
    print("\nAll expected columns present!")

# Verify final state
cursor.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns 
    WHERE table_schema = 'public'
    AND table_name='accounting_auditlog'
    AND column_name IN ('previous_hash_id', 'content_hash', 'organization_id', 'is_immutable')
    ORDER BY column_name
""")

print("\nFinal audit log columns:")
for (col_name, col_type) in cursor.fetchall():
    print(f"  {col_name}: {col_type}")
