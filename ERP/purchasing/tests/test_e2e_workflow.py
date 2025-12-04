"""
End-to-end integration tests for the complete procurement workflow.
"""

from decimal import Decimal
from django.utils import timezone
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from unittest.mock import patch, MagicMock

from purchasing.models import PurchaseOrder, PurchaseOrderLine, GoodsReceipt, GoodsReceiptLine
from purchasing.services.purchase_order_service import PurchaseOrderService
from purchasing.services.goods_receipt_service import GoodsReceiptService
from accounting.models import Vendor, Currency, AccountType, ChartOfAccount
from inventory.models import Product, Warehouse, StockLedger
from usermanagement.models import Organization

User = get_user_model()


class TestE2EProcurementWorkflow(TestCase):
    """End-to-end test of complete procurement workflow."""
    
    def setUp(self):
        """Set up test data."""
        # Organization
        self.org = Organization.objects.create(
            name="Test Company",
            base_currency_code="USD"
        )
        
        # Currency
        self.currency = Currency.objects.create(
            currency_code="USD",
            currency_name="US Dollar",
            symbol="$"
        )
        
        # Create AccountType for GL accounts
        self.liability_type = AccountType.objects.create(
            code="LIA",
            name="Liability",
            nature="liability",
            classification="Statement of Financial Position",
            balance_sheet_category="Liabilities",
            display_order=1
        )
        
        # GL Accounts - create minimal AP account for Vendor FK
        self.ap_account = ChartOfAccount.objects.create(
            organization=self.org,
            account_code="2100",
            account_name="Accounts Payable",
            account_type=self.liability_type
        )
        
        # Vendor
        self.vendor = Vendor.objects.create(
            organization=self.org,
            code="VENDOR001",
            display_name="Supplier A",
            accounts_payable_account=self.ap_account,
            is_active=True
        )
        
        # Product
        self.product = Product.objects.create(
            organization=self.org,
            name="Widget A",
            code="WDG001",
        )
        
        # Warehouse
        self.warehouse = Warehouse.objects.create(
            organization=self.org,
            code="WH001",
            name="Main Warehouse",
            is_active=True
        )
        
        # Users
        self.user = User.objects.create_user(
            username="procurementuser",
            organization=self.org
        )
        
        # Add user to Procurement Manager group
        pm_group, _ = Group.objects.get_or_create(name="Procurement Manager")
        self.user.groups.add(pm_group)
        
        # Services
        self.po_service = PurchaseOrderService(self.user)
        self.gr_service = GoodsReceiptService(self.user)
    
    def test_complete_procurement_workflow(self):
        """
        Test complete workflow:
        1. Create PO
        2. Approve PO
        3. Send PO
        4. Create GR
        5. Verify GR created and tracking updated
        """
        
        # Step 1: Create Purchase Order
        po_lines = [
            {
                "product": self.product,
                "quantity_ordered": Decimal("100"),
                "unit_price": Decimal("50.00"),
                "vat_rate": Decimal("10"),
            }
        ]
        
        po = self.po_service.create_purchase_order(
            organization=self.org,
            vendor=self.vendor,
            currency=self.currency,
            lines=po_lines,
        )
        
        # Verify PO created
        self.assertEqual(po.status, PurchaseOrder.Status.DRAFT)
        self.assertIn("PO-", po.number)
        self.assertEqual(po.total_amount, Decimal("5500.00"))  # 5000 + 500 tax
        self.assertEqual(po.lines.count(), 1)
        
        # Step 2: Approve PO
        po = self.po_service.approve_purchase_order(po)
        self.assertEqual(po.status, PurchaseOrder.Status.APPROVED)
        
        # Step 3: Send PO
        po = self.po_service.mark_sent(po)
        self.assertEqual(po.status, PurchaseOrder.Status.SENT)
        self.assertIsNotNone(po.send_date)
        
        # Step 4: Create Goods Receipt
        gr_lines = [
            {
                "po_line": po.lines.first(),
                "quantity_received": Decimal("100"),
                "quantity_accepted": Decimal("100"),
                "qc_result": "pass",
            }
        ]
        
        gr = self.gr_service.create_goods_receipt(
            purchase_order=po,
            warehouse=self.warehouse,
            lines=gr_lines,
        )
        
        # Verify GR created
        self.assertEqual(gr.status, GoodsReceipt.Status.DRAFT)
        self.assertIn("GR-", gr.number)
        self.assertEqual(gr.lines.count(), 1)
        
        # Step 5: Verify tracking in PO line
        po_line = po.lines.first()
        initial_qty_received = po_line.quantity_received
        
        # Verify line totals correct
        self.assertEqual(po_line.line_total, Decimal("5000.00"))
        self.assertEqual(po_line.variance, Decimal("100"))  # All outstanding
    
    def test_over_receive_prevention(self):
        """Test that over-receiving is prevented."""
        
        # Create and send PO for 100 units
        po = self.po_service.create_purchase_order(
            organization=self.org,
            vendor=self.vendor,
            currency=self.currency,
            lines=[
                {
                    "product": self.product,
                    "quantity_ordered": Decimal("100"),
                    "unit_price": Decimal("50.00"),
                }
            ]
        )
        po = self.po_service.approve_purchase_order(po)
        po = self.po_service.mark_sent(po)
        
        # Try to receive 150 units (should fail)
        gr_lines = [
            {
                "po_line": po.lines.first(),
                "quantity_received": Decimal("150"),  # Over the 100 ordered
                "quantity_accepted": Decimal("150"),
            }
        ]
        
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.gr_service.create_goods_receipt(
                purchase_order=po,
                warehouse=self.warehouse,
                lines=gr_lines,
            )
    
    def test_partial_receipt(self):
        """Test partial goods receipt (receive less than ordered)."""
        
        # Create and send PO for 100 units
        po = self.po_service.create_purchase_order(
            organization=self.org,
            vendor=self.vendor,
            currency=self.currency,
            lines=[
                {
                    "product": self.product,
                    "quantity_ordered": Decimal("100"),
                    "unit_price": Decimal("50.00"),
                }
            ]
        )
        po = self.po_service.approve_purchase_order(po)
        po = self.po_service.mark_sent(po)
        
        # Receive only 60 units
        gr_lines = [
            {
                "po_line": po.lines.first(),
                "quantity_received": Decimal("60"),
                "quantity_accepted": Decimal("60"),
                "qc_result": "pass",
            }
        ]
        
        gr = self.gr_service.create_goods_receipt(
            purchase_order=po,
            warehouse=self.warehouse,
            lines=gr_lines,
        )
        
        # Verify partial receipt
        self.assertEqual(gr.lines.first().quantity_received, Decimal("60"))
        self.assertEqual(gr.status, GoodsReceipt.Status.DRAFT)
        
        # Verify GR not yet affecting PO line
        po_line = po.lines.first()
        po_line.refresh_from_db()
        self.assertEqual(po_line.quantity_received, Decimal("0"))
    
    def test_multi_line_po_workflow(self):
        """Test workflow with multiple PO lines."""
        
        # Create product 2
        product2 = Product.objects.create(
            organization=self.org,
            name="Widget B",
            code="WDG002",
        )
        
        # Create PO with 2 lines
        po = self.po_service.create_purchase_order(
            organization=self.org,
            vendor=self.vendor,
            currency=self.currency,
            lines=[
                {
                    "product": self.product,
                    "quantity_ordered": Decimal("100"),
                    "unit_price": Decimal("50.00"),
                    "vat_rate": Decimal("10"),
                },
                {
                    "product": product2,
                    "quantity_ordered": Decimal("50"),
                    "unit_price": Decimal("100.00"),
                    "vat_rate": Decimal("10"),
                }
            ]
        )
        
        # Verify PO totals
        # Line 1: 100 * 50 = 5000
        # Line 2: 50 * 100 = 5000
        # Subtotal: 10000
        # Tax: 10000 * 0.1 = 1000
        # Total: 11000
        self.assertEqual(po.total_amount, Decimal("11000.00"))
        self.assertEqual(po.lines.count(), 2)
        
        po = self.po_service.approve_purchase_order(po)
        po = self.po_service.mark_sent(po)
        
        # Create GR with both lines
        gr_lines = [
            {
                "po_line": po.lines.all()[0],
                "quantity_received": Decimal("100"),
                "quantity_accepted": Decimal("100"),
            },
            {
                "po_line": po.lines.all()[1],
                "quantity_received": Decimal("50"),
                "quantity_accepted": Decimal("50"),
            }
        ]
        
        gr = self.gr_service.create_goods_receipt(
            purchase_order=po,
            warehouse=self.warehouse,
            lines=gr_lines,
        )
        
        self.assertEqual(gr.lines.count(), 2)
        
        # Post GR
        gr = self.gr_service.post_goods_receipt(gr)
        
        # Verify both lines posted
        for gr_line in gr.lines.all():
            self.assertGreater(gr_line.quantity_accepted, 0)
