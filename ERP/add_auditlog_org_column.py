import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection

cursor = connection.cursor()

# Add organization_id column to accounting_auditlog
print("\nAdding organization_id column to accounting_auditlog...")
try:
    cursor.execute("""
        ALTER TABLE accounting_auditlog 
        ADD COLUMN organization_id BIGINT
    """)
    connection.commit()
    print("OK Column added successfully")
except Exception as e:
    print(f"ERROR adding column: {e}")
    connection.rollback()

# Add foreign key constraint (optional, but good practice)
print("\nAdding foreign key constraint...")
try:
    cursor.execute("""
        ALTER TABLE accounting_auditlog 
        ADD CONSTRAINT accounting_auditlog_organization_id_fkey 
        FOREIGN KEY (organization_id) 
        REFERENCES tenancy_organization(organization_id)
    """)
    connection.commit()
    print("OK Constraint added successfully")
except Exception as e:
    print(f"ERROR adding constraint: {e}")
    connection.rollback()

# Add content_hash column
print("\nAdding content_hash column to accounting_auditlog...")
try:
    cursor.execute("""
        ALTER TABLE accounting_auditlog 
        ADD COLUMN content_hash VARCHAR(64)
    """)
    connection.commit()
    print("OK Column added successfully")
except Exception as e:
    print(f"ERROR adding column: {e}")
    connection.rollback()

# Verify both columns
print("\nVerifying columns...")
cursor.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns 
    WHERE table_schema = 'public'
    AND table_name='accounting_auditlog' 
    AND column_name IN ('organization_id', 'content_hash')
    ORDER BY column_name
""")

for (col_name, col_type) in cursor.fetchall():
    print(f"  {col_name}: {col_type}")
