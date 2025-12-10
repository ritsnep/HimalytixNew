#!/usr/bin/env python
"""
Comprehensive POS Module Testing Script
Tests all POS functionality including models, views, templates, and API endpoints
"""

import os
import sys
import django
from decimal import Decimal
import json

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard.settings')
django.setup()

from django.test import TestCase, Client, RequestFactory
from django.contrib.auth.models import User
from django.urls import reverse
from django.core import mail
from unittest.mock import patch, MagicMock

# POS imports
from pos.models import Cart, CartItem, POSSettings
from pos.views import pos_home, add_to_cart, search_products
from inventory.models import Product
from accounting.models import SalesInvoice, SalesInvoiceLine
from usermanagement.models import Organization, CustomUser


class POSTestingSuite:
    """Comprehensive testing suite for POS module"""

    def __init__(self):
        self.client = Client()
        self.factory = RequestFactory()
        self.user = None
        self.organization = None
        self.product = None
        self.results = []

    def log_result(self, test_name, passed, message=""):
        """Log test result"""
        status = "PASS" if passed else "FAIL"
        self.results.append(f"{status}: {test_name} - {message}")
        print(f"{status}: {test_name}")

    def setup_test_data(self):
        """Setup test data"""
        try:
            # Create test organization
            self.organization, created = Organization.objects.get_or_create(
                name="Test POS Organization",
                defaults={
                    'code': 'TESTPOS',
                    'type': 'retail',
                    'is_active': True,
                    'status': 'active'
                }
            )

            # Create test user
            self.user, created = CustomUser.objects.get_or_create(
                username="test_pos_user",
                defaults={
                    'email': 'test@pos.local',
                    'full_name': 'Test POS User',
                    'organization': self.organization,
                    'is_active': True,
                    'role': 'user'
                }
            )
            if created:
                self.user.set_password('testpass123')
                self.user.save()

            # Create test product
            self.product, created = Product.objects.get_or_create(
                code="TEST001",
                organization=self.organization,
                defaults={
                    'name': 'Test Product',
                    'sale_price': Decimal('10.00'),
                    'cost_price': Decimal('5.00'),
                    'stock_quantity': 100
                }
            )

            # Create POS settings
            POSSettings.objects.get_or_create(
                organization=self.organization,
                defaults={
                    'default_customer_name': 'Walk-in Customer',
                    'enable_barcode_scanner': True,
                    'auto_print_receipt': True,
                }
            )

            self.log_result("Setup test data", True, "Created organization, user, product, and POS settings")
            return True
        except Exception as e:
            import traceback
            print(f"Setup error: {e}")
            traceback.print_exc()
            return False

    def test_models(self):
        """Test POS models"""
        try:
            # Test Cart creation
            cart = Cart.objects.create(
                user=self.user,
                organization=self.organization,
                customer_name='Test Customer'
            )
            self.log_result("Cart model creation", True)

            # Test CartItem creation
            cart_item = CartItem.objects.create(
                cart=cart,
                product_name=self.product.name,
                product_code=self.product.code,
                quantity=Decimal('2.00'),
                unit_price=self.product.sale_price
            )
            self.log_result("CartItem model creation", True)

            # Test cart calculations
            cart.refresh_from_db()
            expected_total = Decimal('20.00')  # 2 * 10.00
            if cart.total == expected_total:
                self.log_result("Cart total calculation", True)
            else:
                self.log_result("Cart total calculation", False, f"Expected {expected_total}, got {cart.total}")

            # Cleanup
            cart_item.delete()
            cart.delete()

            return True
        except Exception as e:
            self.log_result("Models testing", False, f"Error: {str(e)}")
            return False

    def test_views(self):
        """Test POS views"""
        try:
            # Test pos_home view
            self.client.login(username='test_pos_user', password='testpass123')
            response = self.client.get(reverse('pos:pos_home'))

            if response.status_code == 200:
                self.log_result("pos_home view", True)
            else:
                self.log_result("pos_home view", False, f"Status code: {response.status_code}")

            # Test cart API
            response = self.client.get('/pos/api/cart/')
            if response.status_code == 200:
                data = json.loads(response.content)
                if 'cart' in data:
                    self.log_result("Cart API GET", True)
                else:
                    self.log_result("Cart API GET", False, "Missing cart data in response")
            else:
                self.log_result("Cart API GET", False, f"Status code: {response.status_code}")

            # Test add to cart API
            response = self.client.post(
                '/pos/api/cart/add/',
                {'product_code': 'TEST001', 'quantity': 1},
                content_type='application/json'
            )
            if response.status_code == 200:
                data = json.loads(response.content)
                if data.get('success'):
                    self.log_result("Add to cart API", True)
                else:
                    self.log_result("Add to cart API", False, f"Response: {data}")
            else:
                self.log_result("Add to cart API", False, f"Status code: {response.status_code}")

            return True
        except Exception as e:
            self.log_result("Views testing", False, f"Error: {str(e)}")
            return False

    def test_permissions(self):
        """Test POS permissions"""
        try:
            # Test without login
            self.client.logout()
            response = self.client.get(reverse('pos:pos_home'))
            if response.status_code == 302:  # Redirect to login
                self.log_result("POS permission check", True, "Properly redirects unauthenticated users")
            else:
                self.log_result("POS permission check", False, f"Expected redirect, got {response.status_code}")

            return True
        except Exception as e:
            self.log_result("Permissions testing", False, f"Error: {str(e)}")
            return False

    def test_api_endpoints(self):
        """Test all POS API endpoints"""
        try:
            self.client.login(username='test_pos_user', password='testpass123')

            # Test product search
            response = self.client.get('/pos/api/products/search/?q=TEST')
            if response.status_code == 200:
                data = json.loads(response.content)
                if 'products' in data:
                    self.log_result("Product search API", True)
                else:
                    self.log_result("Product search API", False, "Missing products in response")
            else:
                self.log_result("Product search API", False, f"Status code: {response.status_code}")

            # Test popular products
            response = self.client.get('/pos/api/products/top/')
            if response.status_code == 200:
                data = json.loads(response.content)
                if 'products' in data:
                    self.log_result("Popular products API", True)
                else:
                    self.log_result("Popular products API", False, "Missing products in response")
            else:
                self.log_result("Popular products API", False, f"Status code: {response.status_code}")

            # Test cart operations
            # First add item
            response = self.client.post(
                '/pos/api/cart/add/',
                {'product_code': 'TEST001', 'quantity': 2},
                content_type='application/json'
            )
            if response.status_code == 200:
                data = json.loads(response.content)
                if data.get('success'):
                    cart_item_id = None
                    # Get cart to find item ID
                    response = self.client.get('/pos/api/cart/')
                    if response.status_code == 200:
                        cart_data = json.loads(response.content)
                        if cart_data['cart']['items']:
                            cart_item_id = cart_data['cart']['items'][0]['id']

                            # Test update quantity
                            response = self.client.post(
                                '/pos/api/cart/update/',
                                {'item_id': cart_item_id, 'quantity': 3},
                                content_type='application/json'
                            )
                            if response.status_code == 200:
                                self.log_result("Update cart item API", True)
                            else:
                                self.log_result("Update cart item API", False, f"Status: {response.status_code}")

                            # Test remove item
                            response = self.client.post(
                                '/pos/api/cart/remove/',
                                {'item_id': cart_item_id},
                                content_type='application/json'
                            )
                            if response.status_code == 200:
                                self.log_result("Remove cart item API", True)
                            else:
                                self.log_result("Remove cart item API", False, f"Status: {response.status_code}")

                    self.log_result("Add to cart API", True)
                else:
                    self.log_result("Add to cart API", False, f"Response: {data}")
            else:
                self.log_result("Add to cart API", False, f"Status code: {response.status_code}")

            # Test clear cart
            response = self.client.post('/pos/api/cart/clear/', content_type='application/json')
            if response.status_code == 200:
                self.log_result("Clear cart API", True)
            else:
                self.log_result("Clear cart API", False, f"Status code: {response.status_code}")

            return True
        except Exception as e:
            self.log_result("API endpoints testing", False, f"Error: {str(e)}")
            return False

    def test_checkout_process(self):
        """Test the complete checkout process"""
        try:
            self.client.login(username='test_pos_user', password='testpass123')

            # Add item to cart
            response = self.client.post(
                '/pos/api/cart/add/',
                {'product_code': 'TEST001', 'quantity': 1},
                content_type='application/json'
            )

            if response.status_code == 200:
                # Test checkout
                response = self.client.post(
                    '/pos/api/checkout/',
                    {
                        'payment_method': 'cash',
                        'cash_received': '15.00',
                        'customer_name': 'Test Customer'
                    },
                    content_type='application/json'
                )

                if response.status_code == 200:
                    data = json.loads(response.content)
                    if data.get('success'):
                        self.log_result("Checkout process", True, f"Invoice created: {data.get('invoice_number', 'N/A')}")
                    else:
                        self.log_result("Checkout process", False, f"Checkout failed: {data}")
                else:
                    self.log_result("Checkout process", False, f"Status code: {response.status_code}")
            else:
                self.log_result("Checkout process", False, "Failed to add item to cart")

            return True
        except Exception as e:
            self.log_result("Checkout process testing", False, f"Error: {str(e)}")
            return False

    def test_error_handling(self):
        """Test error handling scenarios"""
        try:
            self.client.login(username='test_pos_user', password='testpass123')

            # Test invalid product code
            response = self.client.post(
                '/pos/api/cart/add/',
                {'product_code': 'INVALID', 'quantity': 1},
                content_type='application/json'
            )
            if response.status_code == 200:
                data = json.loads(response.content)
                if not data.get('success'):
                    self.log_result("Invalid product error handling", True)
                else:
                    self.log_result("Invalid product error handling", False, "Should have failed")
            else:
                self.log_result("Invalid product error handling", False, f"Unexpected status: {response.status_code}")

            # Test negative quantity
            response = self.client.post(
                '/pos/api/cart/add/',
                {'product_code': 'TEST001', 'quantity': -1},
                content_type='application/json'
            )
            if response.status_code == 200:
                data = json.loads(response.content)
                if not data.get('success'):
                    self.log_result("Negative quantity error handling", True)
                else:
                    self.log_result("Negative quantity error handling", False, "Should have failed")
            else:
                self.log_result("Negative quantity error handling", False, f"Unexpected status: {response.status_code}")

            return True
        except Exception as e:
            self.log_result("Error handling testing", False, f"Error: {str(e)}")
            return False

    def test_template_rendering(self):
        """Test template rendering"""
        try:
            self.client.login(username='test_pos_user', password='testpass123')
            response = self.client.get(reverse('pos:pos_home'))

            if response.status_code == 200:
                content = response.content.decode('utf-8')

                # Check for key elements
                checks = [
                    ('POS title', 'Point of Sale' in content),
                    ('HTMX wiring', 'hx-get' in content or 'hx-post' in content),
                    ('Cart section', 'Current Order' in content),
                    ('Product search', 'Scan barcode' in content or 'Products' in content),
                    ('Payment section', 'Payment' in content),
                    ('Amount due', 'Amount Due' in content),
                ]

                for check_name, check_result in checks:
                    self.log_result(f"Template rendering - {check_name}", check_result)

                self.log_result("Template rendering", True)
            else:
                self.log_result("Template rendering", False, f"Status code: {response.status_code}")

            return True
        except Exception as e:
            self.log_result("Template rendering testing", False, f"Error: {str(e)}")
            return False

    def run_all_tests(self):
        """Run all POS tests"""
        print("Starting comprehensive POS testing...\n")

        # Setup
        if not self.setup_test_data():
            print("Failed to setup test data. Aborting tests.")
            return

        # Run tests
        test_methods = [
            self.test_models,
            self.test_views,
            self.test_permissions,
            self.test_api_endpoints,
            self.test_checkout_process,
            self.test_error_handling,
            self.test_template_rendering,
        ]

        for test_method in test_methods:
            try:
                test_method()
            except Exception as e:
                self.log_result(test_method.__name__, False, f"Test crashed: {str(e)}")

        # Print results
        print("\n" + "="*50)
        print("POS TESTING RESULTS")
        print("="*50)

        passed = 0
        failed = 0

        for result in self.results:
            print(result)
            if result.startswith("PASS"):
                passed += 1
            else:
                failed += 1

        print(f"\nSUMMARY: {passed} passed, {failed} failed")

        if failed == 0:
            print("🎉 All POS tests passed!")
        else:
            print(f"❌ {failed} test(s) failed. Please review the issues above.")

        return failed == 0


if __name__ == '__main__':
    tester = POSTestingSuite()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)
