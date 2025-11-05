import os
import django
import importlib

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard.settings')
django.setup()

# Force reload the URLs module
import accounting.urls
importlib.reload(accounting.urls)

from accounting import urls

print(f"Total URL patterns: {len(urls.urlpatterns)}")
print(f"\nSearching for journal_config...")

for i, pattern in enumerate(urls.urlpatterns):
    if hasattr(pattern, 'name'):
        if pattern.name == 'journal_config':
            print(f"✓ FOUND at index {i}: name={pattern.name}, pattern={pattern.pattern}")
            break
        elif 'config' in (pattern.name or ''):
            pass  # Skip for now
    elif hasattr(pattern, 'url_patterns'):
        # It's an include()
        for sub_pattern in pattern.url_patterns:
            if hasattr(sub_pattern, 'name') and sub_pattern.name == 'journal_config':
                print(f"✓ FOUND in sub-patterns: {sub_pattern}")
                break
else:
    print("❌ NOT FOUND")
    
print("\n=== Checking lines 90-100 specifically ===")
print("According to the file, lines 90-100 should contain:")
print("91: journal_entry")
print("92: journal_save_draft")
print("93: journal_submit")
print("94: journal_approve")
print("95: journal_reject")
print("96: journal_post")
print("97: journal_config  <-- THIS ONE")
print("98: journal_entry_data")

print("\nActual patterns in urlpatterns (filtered to journal_*):")
journal_patterns = [(i, p.name, str(p.pattern)) for i, p in enumerate(urls.urlpatterns) if hasattr(p, 'name') and p.name and 'journal' in p.name]

for idx, name, pattern in journal_patterns[:20]:  # First 20 journal patterns
    marker = " <-- MISSING" if name == 'journal_config' else ""
    print(f"{idx:3d}: {name:40s} {pattern}{marker}")
