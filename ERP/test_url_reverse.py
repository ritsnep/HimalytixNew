import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard.settings')
django.setup()

from django.urls import reverse, get_resolver

print("=== Testing URL Reverse ===")

# Test without namespace
try:
    url = reverse('journal_config')
    print(f"✓ 'journal_config' (no namespace): {url}")
except Exception as e:
    print(f"❌ 'journal_config' (no namespace): {e}")

# Test with namespace
try:
    url = reverse('accounting:journal_config')
    print(f"✓ 'accounting:journal_config': {url}")
except Exception as e:
    print(f"❌ 'accounting:journal_config': {e}")

print("\n=== All accounting URLs ===")
resolver = get_resolver()
for pattern in resolver.url_patterns:
    if hasattr(pattern, 'namespace') and pattern.namespace == 'accounting':
        for url_pattern in pattern.url_patterns:
            if hasattr(url_pattern, 'name') and url_pattern.name:
                print(f"  - accounting:{url_pattern.name}")
                if 'config' in url_pattern.name:
                    print(f"    Pattern: {url_pattern.pattern}")
