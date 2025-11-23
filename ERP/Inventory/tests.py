from decimal import Decimal

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from usermanagement.models import Organization, CustomUser

from .models import Product, Warehouse, Location, InventoryItem, StockLedger
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
