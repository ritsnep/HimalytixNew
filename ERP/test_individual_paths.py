import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard.settings')
django.setup()

print("=== Testing each path() call individually ===\n")

from django.urls import path
from accounting.views import journal_entry

# Test each URL pattern
urls_to_test = [
    ("journal_approve", 'journal-entry/approve/', journal_entry.journal_approve),
    ("journal_reject", 'journal-entry/reject/', journal_entry.journal_reject),
    ("journal_post", 'journal-entry/post/', journal_entry.journal_post),
    ("journal_config", 'journal-entry/config/', journal_entry.journal_config),
    ("journal_entry_data", 'journal-entry/api/<int:pk>/', journal_entry.journal_entry_data),
]

for name, pattern_str, view_func in urls_to_test:
    try:
        p = path(pattern_str, view_func, name=name)
        print(f"✓ {name:25s} created successfully")
    except Exception as e:
        print(f"❌ {name:25s} FAILED: {e}")

print("\n=== Testing if functions exist ===\n")
functions = ['journal_approve', 'journal_reject', 'journal_post', 'journal_config', 'journal_entry_data']
for func_name in functions:
    if hasattr(journal_entry, func_name):
        func = getattr(journal_entry, func_name)
        print(f"✓ {func_name:25s} exists: {func}")
    else:
        print(f"❌ {func_name:25s} MISSING")
