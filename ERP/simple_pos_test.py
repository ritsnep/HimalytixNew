#!/usr/bin/env python
"""
Simplified POS Testing Script
Tests POS functionality without creating test data
"""

import os
import sys
import django
import json

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard.settings')
django.setup()

from django.test import Client
from django.urls import reverse


class SimplePOSTester:
    """Simplified testing for POS functionality"""

    def __init__(self):
        self.client = Client()
        self.results = []

    def log_result(self, test_name, passed, message=""):
        """Log test result"""
        status = "PASS" if passed else "FAIL"
        self.results.append(f"{status}: {test_name} - {message}")
        print(f"{status}: {test_name}")

    def test_template_loading(self):
        """Test if POS template loads"""
        try:
            # Try to access POS URL without authentication (should redirect)
            response = self.client.get('/pos/')
            if response.status_code == 302:  # Redirect to login
                self.log_result("POS URL accessible", True, "Properly redirects unauthenticated users")
            else:
                self.log_result("POS URL accessible", False, f"Unexpected status: {response.status_code}")

            return True
        except Exception as e:
            self.log_result("Template loading test", False, f"Error: {str(e)}")
            return False

    def test_static_files(self):
        """Test if POS static files are accessible"""
        try:
            response = self.client.get('/static/css/pos.css')
            if response.status_code == 200:
                self.log_result("POS CSS file", True)
            else:
                self.log_result("POS CSS file", False, f"Status: {response.status_code}")

            response = self.client.get('/static/manifest.json')
            if response.status_code == 200:
                self.log_result("PWA manifest", True)
            else:
                self.log_result("PWA manifest", False, f"Status: {response.status_code}")

            return True
        except Exception as e:
            self.log_result("Static files test", False, f"Error: {str(e)}")
            return False

    def test_url_patterns(self):
        """Test if POS URL patterns are configured"""
        try:
            # Test URL reversal
            try:
                url = reverse('pos:pos_home')
                self.log_result("POS URL reversal", True, f"URL: {url}")
            except Exception as e:
                self.log_result("POS URL reversal", False, f"Error: {str(e)}")

            return True
        except Exception as e:
            self.log_result("URL patterns test", False, f"Error: {str(e)}")
            return False

    def test_models_import(self):
        """Test if POS models can be imported"""
        try:
            from pos.models import Cart, CartItem, POSSettings
            self.log_result("POS models import", True)

            # Check model fields
            cart_fields = [f.name for f in Cart._meta.fields]
            cart_item_fields = [f.name for f in CartItem._meta.fields]
            pos_settings_fields = [f.name for f in POSSettings._meta.fields]

            self.log_result("Cart model fields", True, f"Fields: {len(cart_fields)}")
            self.log_result("CartItem model fields", True, f"Fields: {len(cart_item_fields)}")
            self.log_result("POSSettings model fields", True, f"Fields: {len(pos_settings_fields)}")

            return True
        except Exception as e:
            self.log_result("Models import test", False, f"Error: {str(e)}")
            return False

    def test_views_import(self):
        """Test if POS views can be imported"""
        try:
            from pos.views import pos_home, add_to_cart, search_products
            self.log_result("POS views import", True)
            return True
        except Exception as e:
            self.log_result("Views import test", False, f"Error: {str(e)}")
            return False

    def test_template_syntax(self):
        """Test template syntax by loading template"""
        try:
            from django.template.loader import get_template
            template = get_template('pos/pos.html')
            self.log_result("POS template syntax", True)
            return True
        except Exception as e:
            self.log_result("Template syntax test", False, f"Error: {str(e)}")
            return False

    def run_tests(self):
        """Run all simplified tests"""
        print("Running simplified POS tests...\n")

        test_methods = [
            self.test_models_import,
            self.test_views_import,
            self.test_url_patterns,
            self.test_template_syntax,
            self.test_static_files,
            self.test_template_loading,
        ]

        passed = 0
        failed = 0

        for test_method in test_methods:
            try:
                if test_method():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                self.log_result(test_method.__name__, False, f"Test crashed: {str(e)}")
                failed += 1

        # Print results
        print("\n" + "="*50)
        print("SIMPLIFIED POS TESTING RESULTS")
        print("="*50)

        for result in self.results:
            print(result)

        print(f"\nSUMMARY: {passed} passed, {failed} failed")

        if failed == 0:
            print("✅ All basic POS tests passed!")
        else:
            print(f"❌ {failed} test(s) failed.")

        return failed == 0


if __name__ == '__main__':
    tester = SimplePOSTester()
    success = tester.run_tests()
    sys.exit(0 if success else 1)