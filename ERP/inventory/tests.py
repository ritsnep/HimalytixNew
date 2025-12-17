from decimal import Decimal

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from usermanagement.models import Organization, CustomUser

from .models import Product, ProductCategory, Warehouse, Location, InventoryItem, StockLedger
from .services import InventoryService


class StockTransactionViewTests(TestCase):
	def setUp(self):
		self.organization = Organization.objects.create(
			name="Test Org",
			code="TST",
			type="company",
		)
		self.user = CustomUser.objects.create_user(
			username="inventory-user",
			password="pass",
			organization=self.organization,
		)
		self.client.force_login(self.user)

		self.product = Product.objects.create(
			organization=self.organization,
			code="P-100",
			name="Widget",
			uom="ea",
			is_inventory_item=True,
		)
		self.warehouse = Warehouse.objects.create(
			organization=self.organization,
			code="MAIN",
			name="Main Warehouse",
			address_line1="123 Lane",
			city="Austin",
			country_code="US",
		)
		self.location = Location.objects.create(
			warehouse=self.warehouse,
			code="BIN-A",
			name="Primary Bin",
		)

	def test_login_required_for_transactions(self):
		self.client.logout()
		response = self.client.get(reverse('inventory:stock_receipt_create'))
		self.assertEqual(response.status_code, 302)
		self.assertTrue(settings.LOGIN_URL in response.url)

	def test_receipt_flow_updates_inventory(self):
		url = reverse('inventory:stock_receipt_create')
		payload = {
			'product': self.product.pk,
			'warehouse': self.warehouse.pk,
			'location': self.location.pk,
			'reference_id': 'RCPT-001',
			'quantity': '10',
			'unit_cost': '2.50',
			'batch_number': '',
			'serial_number': '',
		}

		response = self.client.post(url, payload)
		self.assertRedirects(response, url)

		item = InventoryItem.objects.get(
			organization=self.organization,
			product=self.product,
			warehouse=self.warehouse,
			location=self.location,
			batch=None,
		)
		self.assertEqual(item.quantity_on_hand, Decimal('10'))
		self.assertEqual(item.unit_cost, Decimal('2.50'))
		self.assertTrue(
			StockLedger.objects.filter(
				organization=self.organization,
				product=self.product,
				txn_type='manual_receipt',
				reference_id='RCPT-001'
			).exists()
		)

	def test_issue_flow_blocks_without_stock(self):
		url = reverse('inventory:stock_issue_create')
		payload = {
			'product': self.product.pk,
			'warehouse': self.warehouse.pk,
			'location': self.location.pk,
			'reference_id': 'ISSUE-001',
			'quantity': '5',
			'batch_number': '',
			'serial_number': '',
			'reason': 'Adjustment',
		}

		response = self.client.post(url, payload)
		self.assertEqual(response.status_code, 200)
		form = response.context['form']
		self.assertIn('No on-hand inventory found', form.errors['__all__'][0])

	def test_issue_flow_reduces_inventory_and_logs_reason(self):
		InventoryService.create_stock_ledger_entry(
			organization=self.organization,
			product=self.product,
			warehouse=self.warehouse,
			location=self.location,
			batch=None,
			txn_type='setup_receipt',
			reference_id='SETUP',
			qty_in=Decimal('15'),
			unit_cost=Decimal('3.00'),
			async_ledger=False,
		)

		url = reverse('inventory:stock_issue_create')
		payload = {
			'product': self.product.pk,
			'warehouse': self.warehouse.pk,
			'location': self.location.pk,
			'reference_id': 'ISSUE-002',
			'quantity': '5',
			'batch_number': '',
			'serial_number': '',
			'reason': 'Damaged goods',
		}

		response = self.client.post(url, payload)
		self.assertRedirects(response, url)

		item = InventoryItem.objects.get(
			organization=self.organization,
			product=self.product,
			warehouse=self.warehouse,
			location=self.location,
			batch=None,
		)
		self.assertEqual(item.quantity_on_hand, Decimal('10'))

		ledger_entry = StockLedger.objects.filter(txn_type='manual_issue').latest('id')
		self.assertEqual(ledger_entry.qty_out, Decimal('5'))
		self.assertIn('Damaged goods', ledger_entry.reference_id)


class InventoryNavigationViewTests(TestCase):
	def setUp(self):
		self.organization = Organization.objects.create(
			name="Nav Org",
			code="NAV",
			type="company",
		)
		self.user = CustomUser.objects.create_user(
			username="nav-user",
			password="pass",
			organization=self.organization,
		)
		self.client.force_login(self.user)

		self.category = ProductCategory.objects.create(
			organization=self.organization,
			code="CAT",
			name="Hardware",
		)
		self.product = Product.objects.create(
			organization=self.organization,
			category=self.category,
			code="NAV-1",
			name="Navigation Widget",
			is_inventory_item=True,
			reorder_level=Decimal('5'),
		)
		self.warehouse = Warehouse.objects.create(
			organization=self.organization,
			code="NAV-WH",
			name="Navigation Warehouse",
			address_line1="1 Main",
			city="Kathmandu",
			country_code="NP",
		)
		self.location = Location.objects.create(
			warehouse=self.warehouse,
			code="NAV-BIN",
			name="Primary",
		)
		InventoryItem.objects.create(
			organization=self.organization,
			product=self.product,
			warehouse=self.warehouse,
			location=self.location,
			quantity_on_hand=Decimal('10'),
			unit_cost=Decimal('1.00'),
		)

	def test_dashboard_context(self):
		response = self.client.get(reverse('inventory:dashboard'))
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context['product_count'], 1)
		self.assertEqual(response.context['warehouse_count'], 1)

	def test_products_view_lists_items(self):
		response = self.client.get(reverse('inventory:products'))
		self.assertContains(response, "Navigation Widget")
		products = response.context['products']
		self.assertEqual(products[0].total_on_hand, Decimal('10'))

	def test_categories_view_lists_category(self):
		response = self.client.get(reverse('inventory:categories'))
		self.assertContains(response, "Hardware")

	def test_warehouses_view_lists_totals(self):
		response = self.client.get(reverse('inventory:warehouses'))
		self.assertEqual(response.status_code, 200)
		warehouses = response.context['warehouses']
		self.assertEqual(warehouses[0].total_on_hand, Decimal('10'))

	def test_stock_movements_requires_org(self):
		StockLedger.objects.create(
			organization=self.organization,
			product=self.product,
			warehouse=self.warehouse,
			location=self.location,
			txn_type='manual_receipt',
			reference_id='TEST',
			txn_date=timezone.now(),
			qty_in=Decimal('2'),
			unit_cost=Decimal('1.00'),
		)
		response = self.client.get(reverse('inventory:stock_movements'))
		self.assertContains(response, 'Recent Movements')

	def test_transfer_views_exposed(self):
		list_url = reverse('inventory:transfer_order_list')
		create_url = reverse('inventory:transfer_order_create')
		self.assertEqual(self.client.get(list_url).status_code, 200)
		self.assertEqual(self.client.get(create_url).status_code, 200)
