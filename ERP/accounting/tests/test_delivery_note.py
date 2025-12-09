from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from accounting.models import DeliveryNote, DeliveryNoteLine, Customer, ChartOfAccount, Currency, AccountType
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
        
        # Create account type
        self.asset_account_type = AccountType.objects.create(
            code='AST',
            name='Asset',
            nature='asset',
            classification='Statement of Financial Position',
            balance_sheet_category='Assets',
            display_order=1,
            root_code_prefix='1000',
            root_code_step=100,
        )
        
        # Create required accounts
        self.ar_account = ChartOfAccount.objects.create(
            organization=self.org,
            account_number='1200',
            account_name='Accounts Receivable',
            account_type=self.asset_account_type,
            is_active=True
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
        
        # Create customer with required accounts_receivable_account
        self.customer = Customer.objects.create(
            organization=self.org,
            code='C001',
            display_name='Test Customer',
            accounts_receivable_account=self.ar_account
        )

    def test_confirm_reduces_stock_and_creates_ledger(self):
        """Test that confirming a delivery note reduces inventory and creates stock ledger entries."""
        dn = DeliveryNote.objects.create(
            organization=self.org,
            customer=self.customer,
            customer_display_name=self.customer.display_name,
            delivery_date=timezone.localdate(),
            warehouse=self.warehouse,
        )
        line = DeliveryNoteLine.objects.create(
            delivery_note=dn,
            line_number=1,
            product=self.product,
            quantity=Decimal('5')
        )

        # Confirm the delivery note
        dn.confirm(user=self.user)

        # Verify inventory was reduced
        inv = InventoryItem.objects.get(organization=self.org, product=self.product, warehouse=self.warehouse)
        self.assertEqual(inv.quantity_on_hand, Decimal('95'))

        # Verify stock ledger entry was created
        ledger = StockLedger.objects.filter(
            organization=self.org,
            product=self.product,
            warehouse=self.warehouse,
            txn_type='delivery_note'
        ).first()
        self.assertIsNotNone(ledger)
        self.assertEqual(ledger.qty_out, Decimal('5'))
        self.assertEqual(ledger.qty_in, Decimal('0'))
        self.assertEqual(ledger.reference_id, dn.note_number or str(dn.delivery_note_id))

    def test_confirm_insufficient_stock_raises_error(self):
        """Test that confirming with insufficient stock raises ValidationError."""
        dn = DeliveryNote.objects.create(
            organization=self.org,
            customer=self.customer,
            customer_display_name=self.customer.display_name,
            delivery_date=timezone.localdate(),
            warehouse=self.warehouse,
        )
        # Try to deliver more than available stock
        line = DeliveryNoteLine.objects.create(
            delivery_note=dn,
            line_number=1,
            product=self.product,
            quantity=Decimal('150')  # More than the 100 available
        )

        with self.assertRaises(ValidationError) as cm:
            dn.confirm(user=self.user)

        self.assertIn('Insufficient stock', str(cm.exception))

        # Verify inventory was not changed
        inv = InventoryItem.objects.get(organization=self.org, product=self.product, warehouse=self.warehouse)
        self.assertEqual(inv.quantity_on_hand, Decimal('100'))

        # Verify no ledger entries were created
        ledger_count = StockLedger.objects.filter(
            organization=self.org,
            product=self.product,
            warehouse=self.warehouse,
            txn_type='delivery_note'
        ).count()
        self.assertEqual(ledger_count, 0)

    def test_confirm_multiple_lines(self):
        """Test confirming delivery note with multiple line items."""
        # Create another product
        product2 = Product.objects.create(
            organization=self.org,
            code='P002',
            name='Test Product 2',
            is_inventory_item=True,
            sale_price=Decimal('20.00'),
            cost_price=Decimal('12.00'),
        )
        InventoryItem.objects.create(
            organization=self.org,
            product=product2,
            warehouse=self.warehouse,
            quantity_on_hand=Decimal('50'),
            unit_cost=Decimal('12.00'),
        )

        dn = DeliveryNote.objects.create(
            organization=self.org,
            customer=self.customer,
            customer_display_name=self.customer.display_name,
            delivery_date=timezone.localdate(),
            warehouse=self.warehouse,
        )
        DeliveryNoteLine.objects.create(
            delivery_note=dn,
            line_number=1,
            product=self.product,
            quantity=Decimal('10')
        )
        DeliveryNoteLine.objects.create(
            delivery_note=dn,
            line_number=2,
            product=product2,
            quantity=Decimal('20')
        )

        dn.confirm(user=self.user)

        # Verify both products' inventory was reduced
        inv1 = InventoryItem.objects.get(organization=self.org, product=self.product, warehouse=self.warehouse)
        self.assertEqual(inv1.quantity_on_hand, Decimal('90'))

        inv2 = InventoryItem.objects.get(organization=self.org, product=product2, warehouse=self.warehouse)
        self.assertEqual(inv2.quantity_on_hand, Decimal('30'))

        # Verify ledger entries for both products
        ledgers = StockLedger.objects.filter(
            organization=self.org,
            warehouse=self.warehouse,
            txn_type='delivery_note'
        ).order_by('product__code')

        self.assertEqual(len(ledgers), 2)
        self.assertEqual(ledgers[0].product, self.product)
        self.assertEqual(ledgers[0].qty_out, Decimal('10'))
        self.assertEqual(ledgers[1].product, product2)
        self.assertEqual(ledgers[1].qty_out, Decimal('20'))

    def test_confirm_no_inventory_item_raises_error(self):
        """Test that confirming delivery note for non-inventory product raises error."""
        # Create a non-inventory product
        non_inv_product = Product.objects.create(
            organization=self.org,
            code='P003',
            name='Service Product',
            is_inventory_item=False,  # Not inventory tracked
            sale_price=Decimal('50.00'),
        )

        dn = DeliveryNote.objects.create(
            organization=self.org,
            customer=self.customer,
            customer_display_name=self.customer.display_name,
            delivery_date=timezone.localdate(),
            warehouse=self.warehouse,
        )
        DeliveryNoteLine.objects.create(
            delivery_note=dn,
            line_number=1,
            product=non_inv_product,
            quantity=Decimal('1')
        )

        with self.assertRaises(ValidationError) as cm:
            dn.confirm(user=self.user)

        self.assertIn('No inventory record', str(cm.exception))

    def test_confirm_empty_delivery_note_raises_error(self):
        """Test that confirming delivery note with no lines raises error."""
        dn = DeliveryNote.objects.create(
            organization=self.org,
            customer=self.customer,
            customer_display_name=self.customer.display_name,
            delivery_date=timezone.localdate(),
            warehouse=self.warehouse,
        )

        with self.assertRaises(ValidationError) as cm:
            dn.confirm(user=self.user)

        self.assertIn('must have at least one line', str(cm.exception))

    def test_confirm_already_confirmed_raises_error(self):
        """Test that confirming an already confirmed delivery note raises error."""
        dn = DeliveryNote.objects.create(
            organization=self.org,
            customer=self.customer,
            customer_display_name=self.customer.display_name,
            delivery_date=timezone.localdate(),
            warehouse=self.warehouse,
        )
        DeliveryNoteLine.objects.create(
            delivery_note=dn,
            line_number=1,
            product=self.product,
            quantity=Decimal('5')
        )

        # First confirm should work
        dn.confirm(user=self.user)
        self.assertEqual(dn.status, 'confirmed')

        # Second confirm should fail
        with self.assertRaises(ValidationError) as cm:
            dn.confirm(user=self.user)

        self.assertIn('Only draft delivery notes can be confirmed', str(cm.exception))

    def test_confirm_updates_delivery_note_status(self):
        """Test that confirming updates the delivery note status."""
        dn = DeliveryNote.objects.create(
            organization=self.org,
            customer=self.customer,
            customer_display_name=self.customer.display_name,
            delivery_date=timezone.localdate(),
            warehouse=self.warehouse,
            status='draft'
        )
        DeliveryNoteLine.objects.create(
            delivery_note=dn,
            line_number=1,
            product=self.product,
            quantity=Decimal('5')
        )

        dn.confirm(user=self.user)

        dn.refresh_from_db()
        self.assertEqual(dn.status, 'confirmed')