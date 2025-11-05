import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard.settings')
django.setup()

print("=== Testing import ===")

try:
    from accounting.views import journal_entry
    print(f"✓ Imported journal_entry module: {journal_entry}")
    
    if hasattr(journal_entry, 'journal_config'):
        print(f"✓ journal_config function exists: {journal_entry.journal_config}")
    else:
        print("❌ journal_config function NOT found in journal_entry module")
        print(f"   Available functions: {[x for x in dir(journal_entry) if not x.startswith('_')]}")
except Exception as e:
    print(f"❌ Error importing: {e}")
    import traceback
    traceback.print_exc()

print("\n=== Testing URL import ===")
try:
    from accounting import urls
    print(f"✓ Imported accounting.urls module")
    print(f"   Number of URL patterns: {len(urls.urlpatterns)}")
    
    # Find journal_config in urlpatterns
    found = False
    for pattern in urls.urlpatterns:
        if hasattr(pattern, 'name') and pattern.name == 'journal_config':
            print(f"✓ Found journal_config pattern: {pattern.pattern}")
            found = True
            break
    
    if not found:
        print("❌ journal_config NOT found in urlpatterns")
        print("\n   Available URL names containing 'config':")
        for pattern in urls.urlpatterns:
            if hasattr(pattern, 'name') and pattern.name and 'config' in pattern.name:
                print(f"     - {pattern.name}: {pattern.pattern}")
                
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
