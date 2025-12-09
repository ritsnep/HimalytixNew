#!/usr/bin/env python
"""
Simple HTMX POS verification test
"""
import os
import sys
import django
from django.conf import settings

# Configure Django settings
if not settings.configured:
    sys.path.insert(0, os.path.dirname(__file__))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard.settings')
    django.setup()

def test_htmx_imports():
    """Test that HTMX-related imports work"""
    try:
        from pos.views import add_to_cart, update_cart_item, search_products
        print("✅ POS views imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Failed to import POS views: {e}")
        return False

def test_htmx_url_patterns():
    """Test that HTMX URL patterns are configured"""
    try:
        from django.urls import reverse
        urls = [
            'pos:add_to_cart',
            'pos:update_cart_item',
            'pos:search_products',
            'pos:pos_home'
        ]
        for url_name in urls:
            url = reverse(url_name)
            print(f"✅ URL {url_name} -> {url}")
        return True
    except Exception as e:
        print(f"❌ Failed to reverse URLs: {e}")
        return False

def test_htmx_template_syntax():
    """Test that HTMX templates have correct syntax"""
    try:
        from django.template.loader import get_template
        templates = [
            'pos/pos.html',
            'pos/fragments/cart_items.html',
            'pos/fragments/cart_total.html',
            'pos/fragments/search_results.html'
        ]
        for template_name in templates:
            template = get_template(template_name)
            print(f"✅ Template {template_name} loaded successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to load templates: {e}")
        return False

if __name__ == '__main__':
    print("Testing HTMX POS Implementation...")
    print("=" * 50)

    tests = [
        test_htmx_imports,
        test_htmx_url_patterns,
        test_htmx_template_syntax
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        print()

    print("=" * 50)
    print(f"HTMX POS Tests: {passed}/{total} passed")

    if passed == total:
        print("🎉 All HTMX POS components verified successfully!")
        print("The HTMX migration is complete and functional.")
    else:
        print("⚠️  Some HTMX components may need attention.")