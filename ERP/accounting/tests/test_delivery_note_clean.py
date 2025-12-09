from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from accounting.models import DeliveryNote, DeliveryNoteLine
from inventory.models import Product, Warehouse, InventoryItem, StockLedger
from usermanagement.models import Organization

User = get_user_model()


class DeliveryNoteConfirmTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Test Org')
        self.user = User.objects.create(username='tester')
        self.warehouse = Warehouse.objects.create(
            organization=self.org,
            code='WH1',
            name='Main',
            address_line1='addr',
            city='city',
            country_code='US',
        )
        self.product = Product.objects.create(
            organization=self.org,
            code='P001',
            name='Test Product',
            is_inventory_item=True,
            sale_price=Decimal('10.00'),
            cost_price=Decimal('6.00'),
        )
        InventoryItem.objects.create(
            organization=self.org,
            product=self.product,
            warehouse=self.warehouse,
            quantity_on_hand=Decimal('100'),
            unit_cost=Decimal('6.00'),
        )
        self.customer = None

    def test_confirm_reduces_stock_and_creates_ledger(self):
        # create a dummy customer
        from accounting.models import Customer

        customer = Customer.objects.create(organization=self.org, code='C001', display_name='Acme')
        dn = DeliveryNote.objects.create(
            organization=self.org,
            customer=customer,
            customer_display_name=customer.display_name,
            delivery_date=timezone.localdate(),
            warehouse=self.warehouse,
        )
        line = DeliveryNoteLine.objects.create(delivery_note=dn, line_number=1, product=self.product, quantity=Decimal('5'))
        # confirm
        dn.confirm(user=self.user)
        inv = InventoryItem.objects.get(organization=self.org, product=self.product, warehouse=self.warehouse)
        self.assertEqual(inv.quantity_on_hand, Decimal('95'))
        ledger = StockLedger.objects.filter(
            organization=self.org, product=self.product, warehouse=self.warehouse, txn_type='delivery_note'
        ).first()
        self.assertIsNotNone(ledger)
        self.assertEqual(ledger.qty_out, Decimal('5'))
