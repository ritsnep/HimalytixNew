"""
Unit tests for Purchase Order and Goods Receipt models & services.
"""

import pytest
from decimal import Decimal
from datetime import date

from django.utils import timezone
from django.test import TestCase
from django.core.exceptions import ValidationError

from purchasing.models import PurchaseOrder, PurchaseOrderLine, GoodsReceipt, GoodsReceiptLine
from purchasing.services.purchase_order_service import PurchaseOrderService
from purchasing.services.goods_receipt_service import GoodsReceiptService
from accounting.models import Vendor, Currency, ChartOfAccount, FiscalYear, AccountingPeriod
from inventory.models import Product, Warehouse, StockLedger
from usermanagement.models import Organization
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestPurchaseOrderModel:
    """Test PurchaseOrder model creation and calculations."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test data."""
        self.org = Organization.objects.create(
            name="Test Org",
            base_currency_code="USD"
        )
        self.currency = Currency.objects.create(
            currency_code="USD",
            currency_name="US Dollar",
            symbol="$"
        )
        self.vendor = Vendor.objects.create(
            organization=self.org,
            code="VENDOR001",
            display_name="Test Vendor",
            is_active=True
        )
        self.user = User.objects.create_user(
            username="testuser",
            organization=self.org
        )
    
    def test_create_purchase_order(self):
        """Test creating a purchase order."""
        po = PurchaseOrder.objects.create(
            organization=self.org,
            vendor=self.vendor,
            number="PO-2024-000001",
            order_date=timezone.now().date(),
            currency=self.currency,
            created_by=self.user,
        )
        
        assert po.status == PurchaseOrder.Status.DRAFT
        assert po.total_amount == Decimal("0")
    
    def test_po_recalc_totals(self):
        """Test PO total calculation."""
        po = PurchaseOrder.objects.create(
            organization=self.org,
            vendor=self.vendor,
            number="PO-2024-000001",
            order_date=timezone.now().date(),
            currency=self.currency,
            created_by=self.user,
        )
        
        product = Product.objects.create(
            organization=self.org,
            name="Widget",
            code="WDG001",
        )
        
        # Add line items
        PurchaseOrderLine.objects.create(
            purchase_order=po,
            product=product,
            quantity_ordered=Decimal("10"),
            unit_price=Decimal("100.00"),
            vat_rate=Decimal("10"),
        )
        
        PurchaseOrderLine.objects.create(
            purchase_order=po,
            product=product,
            quantity_ordered=Decimal("5"),
            unit_price=Decimal("50.00"),
            vat_rate=Decimal("10"),
        )
        
        po.recalc_totals()
        po.save(skip_recalc=True)
        
        # Subtotal: (10*100) + (5*50) = 1250
        # Tax: 1250 * 0.1 = 125
        # Total: 1375
        assert po.subtotal == Decimal("1250.00")
        assert po.tax_amount == Decimal("125.00")
        assert po.total_amount == Decimal("1375.00")
    
    def test_po_status_transitions(self):
        """Test valid PO status transitions."""
        po = PurchaseOrder.objects.create(
            organization=self.org,
            vendor=self.vendor,
            number="PO-2024-000001",
            order_date=timezone.now().date(),
            currency=self.currency,
            created_by=self.user,
            status=PurchaseOrder.Status.DRAFT,
        )
        
        # DRAFT -> APPROVED
        po.status = PurchaseOrder.Status.APPROVED
        po.save()
        assert po.status == PurchaseOrder.Status.APPROVED
        
        # APPROVED -> SENT
        po.status = PurchaseOrder.Status.SENT
        po.save()
        assert po.status == PurchaseOrder.Status.SENT


@pytest.mark.django_db
class TestPurchaseOrderService:
    """Test PurchaseOrderService business logic."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test data."""
        self.org = Organization.objects.create(
            name="Test Org",
            base_currency_code="USD"
        )
        self.currency = Currency.objects.create(
            currency_code="USD",
            currency_name="US Dollar",
            symbol="$"
        )
        self.vendor = Vendor.objects.create(
            organization=self.org,
            code="VENDOR001",
            display_name="Test Vendor",
            is_active=True
        )
        self.product = Product.objects.create(
            organization=self.org,
            name="Widget",
            code="WDG001",
        )
        self.user = User.objects.create_user(
            username="testuser",
            organization=self.org
        )
        self.service = PurchaseOrderService(self.user)
    
    def test_create_purchase_order(self):
        """Test creating a PO via service."""
        lines = [
            {
                "product": self.product,
                "quantity_ordered": Decimal("10"),
                "unit_price": Decimal("100.00"),
                "vat_rate": Decimal("10"),
            }
        ]
        
        po = self.service.create_purchase_order(
            organization=self.org,
            vendor=self.vendor,
            lines=lines,
            currency=self.currency,
        )
        
        assert po.status == PurchaseOrder.Status.DRAFT
        assert po.total_amount == Decimal("1100.00")  # 1000 + 100 tax
        assert po.lines.count() == 1
    
    def test_approve_purchase_order(self):
        """Test approving a PO."""
        po = PurchaseOrder.objects.create(
            organization=self.org,
            vendor=self.vendor,
            number="PO-2024-000001",
            order_date=timezone.now().date(),
            currency=self.currency,
            created_by=self.user,
            status=PurchaseOrder.Status.DRAFT,
        )
        
        po = self.service.approve_purchase_order(po)
        assert po.status == PurchaseOrder.Status.APPROVED
    
    def test_mark_sent(self):
        """Test marking PO as sent."""
        po = PurchaseOrder.objects.create(
            organization=self.org,
            vendor=self.vendor,
            number="PO-2024-000001",
            order_date=timezone.now().date(),
            currency=self.currency,
            created_by=self.user,
            status=PurchaseOrder.Status.APPROVED,
        )
        
        po = self.service.mark_sent(po)
        assert po.status == PurchaseOrder.Status.SENT
        assert po.send_date is not None
    
    def test_po_number_generation(self):
        """Test PO number auto-generation."""
        lines = [
            {
                "product": self.product,
                "quantity_ordered": Decimal("10"),
                "unit_price": Decimal("100.00"),
            }
        ]
        
        po1 = self.service.create_purchase_order(
            organization=self.org,
            vendor=self.vendor,
            lines=lines,
            currency=self.currency,
        )
        
        po2 = self.service.create_purchase_order(
            organization=self.org,
            vendor=self.vendor,
            lines=lines,
            currency=self.currency,
        )
        
        # Should have sequential PO numbers
        assert po1.number != po2.number
        assert "PO-" in po1.number


@pytest.mark.django_db
class TestGoodsReceiptModel:
    """Test GoodsReceipt model creation and tracking."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test data."""
        self.org = Organization.objects.create(
            name="Test Org",
            base_currency_code="USD"
        )
        self.currency = Currency.objects.create(
            currency_code="USD",
            currency_name="US Dollar",
            symbol="$"
        )
        self.vendor = Vendor.objects.create(
            organization=self.org,
            code="VENDOR001",
            display_name="Test Vendor",
            is_active=True
        )
        self.warehouse = Warehouse.objects.create(
            organization=self.org,
            code="WH001",
            name="Main Warehouse",
            is_active=True
        )
        self.product = Product.objects.create(
            organization=self.org,
            name="Widget",
            code="WDG001",
        )
        self.user = User.objects.create_user(
            username="testuser",
            organization=self.org
        )
        
        # Create a PO
        self.po = PurchaseOrder.objects.create(
            organization=self.org,
            vendor=self.vendor,
            number="PO-2024-000001",
            order_date=timezone.now().date(),
            currency=self.currency,
            created_by=self.user,
            status=PurchaseOrder.Status.SENT,
        )
        
        self.po_line = PurchaseOrderLine.objects.create(
            purchase_order=self.po,
            product=self.product,
            quantity_ordered=Decimal("100"),
            unit_price=Decimal("50.00"),
        )
    
    def test_create_goods_receipt(self):
        """Test creating a goods receipt."""
        gr = GoodsReceipt.objects.create(
            organization=self.org,
            purchase_order=self.po,
            warehouse=self.warehouse,
            number="GR-2024-000001",
            receipt_date=timezone.now().date(),
            created_by=self.user,
        )
        
        assert gr.status == GoodsReceipt.Status.DRAFT
        assert gr.journal is None  # Not posted yet
    
    def test_gr_line_creation(self):
        """Test creating GR line items."""
        gr = GoodsReceipt.objects.create(
            organization=self.org,
            purchase_order=self.po,
            warehouse=self.warehouse,
            number="GR-2024-000001",
            receipt_date=timezone.now().date(),
            created_by=self.user,
        )
        
        gr_line = GoodsReceiptLine.objects.create(
            receipt=gr,
            po_line=self.po_line,
            quantity_received=Decimal("50"),
            quantity_accepted=Decimal("50"),
            qc_result="pass",
        )
        
        assert gr_line.quantity_received == Decimal("50")
        assert gr_line.quantity_accepted == Decimal("50")
        assert gr_line.qc_result == "pass"


@pytest.mark.django_db
class TestGoodsReceiptService:
    """Test GoodsReceiptService business logic."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test data."""
        self.org = Organization.objects.create(
            name="Test Org",
            base_currency_code="USD"
        )
        self.currency = Currency.objects.create(
            currency_code="USD",
            currency_name="US Dollar",
            symbol="$"
        )
        self.vendor = Vendor.objects.create(
            organization=self.org,
            code="VENDOR001",
            display_name="Test Vendor",
            is_active=True
        )
        self.warehouse = Warehouse.objects.create(
            organization=self.org,
            code="WH001",
            name="Main Warehouse",
            is_active=True
        )
        self.product = Product.objects.create(
            organization=self.org,
            name="Widget",
            code="WDG001",
        )
        self.user = User.objects.create_user(
            username="testuser",
            organization=self.org
        )
        
        # Create GL account for testing
        self.ap_account = ChartOfAccount.objects.create(
            organization=self.org,
            code="2100",
            account_name="Accounts Payable",
            account_type="liability"
        )
        
        # Create a PO
        self.po = PurchaseOrder.objects.create(
            organization=self.org,
            vendor=self.vendor,
            number="PO-2024-000001",
            order_date=timezone.now().date(),
            currency=self.currency,
            created_by=self.user,
            status=PurchaseOrder.Status.SENT,
        )
        
        self.po_line = PurchaseOrderLine.objects.create(
            purchase_order=self.po,
            product=self.product,
            quantity_ordered=Decimal("100"),
            unit_price=Decimal("50.00"),
        )
        
        self.service = GoodsReceiptService(self.user)
    
    def test_create_goods_receipt(self):
        """Test creating a GR via service."""
        lines = [
            {
                "po_line": self.po_line,
                "quantity_received": Decimal("50"),
                "quantity_accepted": Decimal("50"),
                "qc_result": "pass",
            }
        ]
        
        gr = self.service.create_goods_receipt(
            purchase_order=self.po,
            warehouse=self.warehouse,
            lines=lines,
        )
        
        assert gr.status == GoodsReceipt.Status.DRAFT
        assert gr.lines.count() == 1
        assert gr.lines.first().quantity_received == Decimal("50")
    
    def test_cannot_over_receive(self):
        """Test that over-receiving is prevented."""
        lines = [
            {
                "po_line": self.po_line,
                "quantity_received": Decimal("150"),  # More than ordered
                "quantity_accepted": Decimal("150"),
            }
        ]
        
        with pytest.raises(ValidationError):
            self.service.create_goods_receipt(
                purchase_order=self.po,
                warehouse=self.warehouse,
                lines=lines,
            )

    def test_post_goods_receipt_creates_ledger_and_journal(self, monkeypatch):
        """Posting a GR creates stock ledger entries and a journal."""
        today = timezone.now().date()
        fiscal_year = FiscalYear.objects.create(
            organization=self.org,
            code="FY",
            name="FY",
            start_date=date(today.year, 1, 1),
            end_date=date(today.year, 12, 31),
            status="open",
        )
        AccountingPeriod.objects.create(
            fiscal_year=fiscal_year,
            organization=self.org,
            period_number=1,
            name="P1",
            start_date=date(today.year, 1, 1),
            end_date=date(today.year, 12, 31),
            status="open",
        )
        inventory_account = ChartOfAccount.objects.create(
            organization=self.org,
            code="1200",
            account_name="Inventory",
            account_type="asset",
        )
        ChartOfAccount.objects.create(
            organization=self.org,
            code="2101",
            account_name="AP Clearing",
            account_type="liability",
        )
        self.product.inventory_account = inventory_account
        self.product.is_inventory_item = True
        self.product.save(update_fields=["inventory_account", "is_inventory_item"])

        lines = [
            {
                "po_line": self.po_line,
                "quantity_received": Decimal("10"),
                "quantity_accepted": Decimal("10"),
            }
        ]
        gr = self.service.create_goods_receipt(
            purchase_order=self.po,
            warehouse=self.warehouse,
            lines=lines,
            receipt_date=today,
        )
        monkeypatch.setattr(
            "accounting.services.posting_service.PostingService.post",
            lambda _self, journal: journal,
        )

        posted = self.service.post_goods_receipt(gr)

        assert posted.status == GoodsReceipt.Status.POSTED
        assert posted.journal is not None
        ledger_entry = StockLedger.objects.filter(reference_id=posted.number).first()
        assert ledger_entry is not None
        assert ledger_entry.qty_in == Decimal("10")
        assert ledger_entry.txn_type == "goods_receipt"


class TestPurchaseOrderIntegration(TestCase):
    """Integration tests for complete workflows."""
    
    def setUp(self):
        """Set up test data."""
        self.org = Organization.objects.create(
            name="Test Org",
            base_currency_code="USD"
        )
        self.currency = Currency.objects.create(
            currency_code="USD",
            currency_name="US Dollar",
            symbol="$"
        )
        self.vendor = Vendor.objects.create(
            organization=self.org,
            code="VENDOR001",
            display_name="Test Vendor",
            is_active=True
        )
        self.product = Product.objects.create(
            organization=self.org,
            name="Widget",
            code="WDG001",
        )
        self.user = User.objects.create_user(
            username="testuser",
            organization=self.org
        )
        self.po_service = PurchaseOrderService(self.user)
    
    def test_full_po_workflow(self):
        """Test complete PO workflow: create -> approve -> send."""
        lines = [
            {
                "product": self.product,
                "quantity_ordered": Decimal("100"),
                "unit_price": Decimal("50.00"),
                "vat_rate": Decimal("10"),
            }
        ]
        
        # Create PO
        po = self.po_service.create_purchase_order(
            organization=self.org,
            vendor=self.vendor,
            lines=lines,
            currency=self.currency,
        )
        self.assertEqual(po.status, PurchaseOrder.Status.DRAFT)
        
        # Approve PO
        po = self.po_service.approve_purchase_order(po)
        self.assertEqual(po.status, PurchaseOrder.Status.APPROVED)
        
        # Send PO
        po = self.po_service.mark_sent(po)
        self.assertEqual(po.status, PurchaseOrder.Status.SENT)
        self.assertIsNotNone(po.send_date)
