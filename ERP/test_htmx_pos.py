#!/usr/bin/env python
"""
Test HTMX POS functionality
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

from django.test import TestCase, Client
from django.urls import reverse
from usermanagement.models import CustomUser as User
from pos.models import Cart, CartItem
from inventory.models import Product as InventoryProduct

class HTMXPOSTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client.login(username='testuser', password='testpass')

        # Create test product
        self.product = InventoryProduct.objects.create(
            name='Test Product',
            sku='TEST001',
            price=10.00,
            stock_quantity=100
        )

    def test_htmx_cart_add(self):
        """Test adding item to cart via HTMX"""
        url = reverse('pos:add_to_cart')
        response = self.client.post(url, {
            'product_id': self.product.id,
            'quantity': 1
        }, HTTP_HX_REQUEST='true')

        self.assertEqual(response.status_code, 200)
        self.assertIn('hx-swap-oob', response.content.decode())

    def test_htmx_cart_update(self):
        """Test updating cart item quantity via HTMX"""
        # First add item to cart
        cart = Cart.objects.create(user=self.user)
        cart_item = CartItem.objects.create(
            cart=cart,
            product=self.product,
            quantity=1,
            price=self.product.price
        )

        url = reverse('pos:update_cart_item', kwargs={'item_id': cart_item.id})
        response = self.client.post(url, {
            'quantity': 2
        }, HTTP_HX_REQUEST='true')

        self.assertEqual(response.status_code, 200)
        cart_item.refresh_from_db()
        self.assertEqual(cart_item.quantity, 2)

    def test_htmx_search_products(self):
        """Test product search via HTMX"""
        url = reverse('pos:search_products')
        response = self.client.get(url, {
            'q': 'Test'
        }, HTTP_HX_REQUEST='true')

        self.assertEqual(response.status_code, 200)
        self.assertIn('Test Product', response.content.decode())

if __name__ == '__main__':
    import unittest
    unittest.main()