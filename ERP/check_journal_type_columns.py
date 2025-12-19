import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection

cursor = connection.cursor()

cursor.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_schema = 'public'
    AND table_name = 'journal_type' 
    ORDER BY ordinal_position
""")

print("\nJournalType table columns:")
print("=" * 70)
for col_name, col_type in cursor.fetchall():
    print(f"{col_name:40} {col_type}")
