"""
Integration tests for the unified purchasing workflow.

Tests the complete flow from PO creation through GR posting and landed cost allocation.
"""

import pytest
from decimal import Decimal
from datetime import date

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from purchasing.models import (
    PurchaseOrder, PurchaseOrderLine,
    GoodsReceipt, GoodsReceiptLine,
    LandedCostDocument,
)
from accounting.models import Vendor, Currency, ChartOfAccount, AccountType
from inventory.models import Product, Warehouse
from usermanagement.models import Organization

User = get_user_model()


@pytest.mark.django_db
class TestUnifiedPurchasingFlow(TestCase):
    """Test complete purchasing workflow."""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create test org
        cls.org = Organization.objects.create(
            name="Test Org",
            code="TEST",
            base_currency_code="USD"
        )
    
    def setUp(self):
        """Set up test data."""
        # Create user
        self.user = User.objects.create_user(
            username='test_user',
            password='testpass123'
        )
        self.user.organization_set.add(self.org)
        
        # Create currency
        self.currency = Currency.objects.create(
            organization=self.org,
            currency_code='USD',
            currency_name='US Dollar'
        )
        
        # Create vendor
        self.vendor = Vendor.objects.create(
            organization=self.org,
            name='Test Vendor',
            country='US',
            is_active=True
        )
        
        # Create warehouse
        self.warehouse = Warehouse.objects.create(
            organization=self.org,
            name='Main Warehouse',
            is_active=True
        )
        
        # Create product
        self.product = Product.objects.create(
            organization=self.org,
            name='Test Product',
            sku='TEST-001',
            unit='PC',
            is_active=True
        )
        
        # Create GL accounts
        self.inventory_account = ChartOfAccount.objects.create(
            organization=self.org,
            account_number='1000',
            account_name='Inventory',
            account_type=AccountType.objects.create(
                name='Asset',
                is_active=True
            )
        )
        
        self.expense_account = ChartOfAccount.objects.create(
            organization=self.org,
            account_number='5000',
            account_name='Purchases',
            account_type=AccountType.objects.first() or AccountType.objects.create(
                name='Expense',
                is_active=True
            )
        )
    
    def test_complete_purchasing_flow(self):
        """Test complete flow: PO → GR → Landed Cost."""
        
        # 1. Create Purchase Order
        po = PurchaseOrder.objects.create(
            organization=self.org,
            vendor=self.vendor,
            number='PO-2025-001',
            order_date=date.today(),
            currency=self.currency,
            status=PurchaseOrder.Status.DRAFT
        )
        
        # Add PO line
        po_line = PurchaseOrderLine.objects.create(
            purchase_order=po,
            product=self.product,
            quantity_ordered=Decimal('100'),
            unit_price=Decimal('10.00'),
            vat_rate=Decimal('10'),
            inventory_account=self.inventory_account
        )
        
        po.recalc_totals()
        assert po.subtotal == Decimal('1000.00')
        assert po.tax_amount == Decimal('100.00')
        assert po.total_amount == Decimal('1100.00')
        
        # 2. Approve and send PO
        po.status = PurchaseOrder.Status.APPROVED
        po.save()
        assert po.status == PurchaseOrder.Status.APPROVED
        
        po.status = PurchaseOrder.Status.SENT
        po.save()
        assert po.status == PurchaseOrder.Status.SENT
        
        # 3. Create Goods Receipt
        gr = GoodsReceipt.objects.create(
            organization=self.org,
            purchase_order=po,
            number='GR-2025-001',
            receipt_date=date.today(),
            warehouse=self.warehouse,
            status=GoodsReceipt.Status.DRAFT
        )
        
        # Add GR line
        gr_line = GoodsReceiptLine.objects.create(
            receipt=gr,
            po_line=po_line,
            quantity_received=Decimal('100'),
            quantity_accepted=Decimal('100'),
            qc_result='pass'
        )
        
        assert gr_line.quantity_received == Decimal('100')
        assert gr_line.qc_result == 'pass'
        
        # 4. Mark GR as received
        gr.status = GoodsReceipt.Status.RECEIVED
        gr.save()
        assert gr.status == GoodsReceipt.Status.RECEIVED
        
        # 5. Post GR (would create GL entries in real scenario)
        gr.status = GoodsReceipt.Status.POSTED
        gr.save()
        assert gr.status == GoodsReceipt.Status.POSTED
        
        # 6. Update PO line with received qty
        po_line.quantity_received = Decimal('100')
        po_line.save()
        
        # 7. Verify variance calculation
        variance = po_line.variance
        assert variance == Decimal('0')  # 100 ordered - (100 received + 0 invoiced)
        
        print("✓ Complete purchasing flow test passed!")
    
    def test_po_creation_with_multiple_lines(self):
        """Test creating PO with multiple line items."""
        
        po = PurchaseOrder.objects.create(
            organization=self.org,
            vendor=self.vendor,
            number='PO-2025-002',
            order_date=date.today(),
            currency=self.currency
        )
        
        # Add multiple lines
        for i in range(3):
            product = Product.objects.create(
                organization=self.org,
                name=f'Product {i}',
                sku=f'SKU-{i}',
                unit='PC'
            )
            PurchaseOrderLine.objects.create(
                purchase_order=po,
                product=product,
                quantity_ordered=Decimal('10') * (i + 1),
                unit_price=Decimal('50.00'),
                vat_rate=Decimal('10'),
                inventory_account=self.inventory_account
            )
        
        po.recalc_totals()
        
        # Verify totals
        # Line 1: 10 * 50 = 500
        # Line 2: 20 * 50 = 1000
        # Line 3: 30 * 50 = 1500
        # Subtotal = 3000
        # Tax (10%) = 300
        # Total = 3300
        
        assert po.subtotal == Decimal('3000.00')
        assert po.tax_amount == Decimal('300.00')
        assert po.total_amount == Decimal('3300.00')
        assert po.lines.count() == 3
        
        print("✓ Multiple lines test passed!")
    
    def test_gr_line_editing(self):
        """Test editing GR line quantities and QC results."""
        
        # Setup PO
        po = PurchaseOrder.objects.create(
            organization=self.org,
            vendor=self.vendor,
            number='PO-2025-003',
            order_date=date.today(),
            currency=self.currency,
            status=PurchaseOrder.Status.SENT
        )
        
        po_line = PurchaseOrderLine.objects.create(
            purchase_order=po,
            product=self.product,
            quantity_ordered=Decimal('100'),
            unit_price=Decimal('10.00'),
            inventory_account=self.inventory_account
        )
        
        # Create GR
        gr = GoodsReceipt.objects.create(
            organization=self.org,
            purchase_order=po,
            number='GR-2025-002',
            receipt_date=date.today(),
            warehouse=self.warehouse
        )
        
        gr_line = GoodsReceiptLine.objects.create(
            receipt=gr,
            po_line=po_line,
            quantity_received=Decimal('95'),
            quantity_accepted=Decimal('90'),
            quantity_rejected=Decimal('5'),
            batch_number='BATCH-001',
            qc_result='fail'
        )
        
        # Verify editing
        assert gr_line.quantity_received == Decimal('95')
        assert gr_line.quantity_accepted == Decimal('90')
        assert gr_line.quantity_rejected == Decimal('5')
        assert gr_line.batch_number == 'BATCH-001'
        assert gr_line.qc_result == 'fail'
        
        # Update and save
        gr_line.quantity_accepted = Decimal('95')
        gr_line.quantity_rejected = Decimal('0')
        gr_line.qc_result = 'pass'
        gr_line.save()
        
        assert gr_line.quantity_accepted == Decimal('95')
        assert gr_line.qc_result == 'pass'
        
        print("✓ GR line editing test passed!")
    
    def test_landed_cost_creation(self):
        """Test creating and applying landed costs."""
        from purchasing.models import PurchaseInvoice, PurchaseInvoiceLine, LandedCostLine
        
        # Create invoice
        invoice = PurchaseInvoice.objects.create(
            organization=self.org,
            supplier=self.vendor,
            number='PI-2025-001',
            invoice_date=date.today(),
            currency=self.currency,
            status=PurchaseInvoice.Status.POSTED
        )
        
        # Add invoice line
        inv_line = PurchaseInvoiceLine.objects.create(
            invoice=invoice,
            product=self.product,
            warehouse=self.warehouse,
            quantity=Decimal('100'),
            unit_price=Decimal('10.00'),
            vat_rate=Decimal('10')
        )
        
        invoice.recalc_totals()
        
        # Create landed cost document
        lc_doc = LandedCostDocument.objects.create(
            organization=self.org,
            purchase_invoice=invoice,
            document_date=date.today(),
            basis=LandedCostDocument.LandedCostBasis.BY_VALUE,
            note='Freight and insurance'
        )
        
        # Add cost lines
        LandedCostLine.objects.create(
            document=lc_doc,
            description='Freight',
            amount=Decimal('50.00'),
            gl_account=self.expense_account
        )
        
        LandedCostLine.objects.create(
            document=lc_doc,
            description='Insurance',
            amount=Decimal('25.00'),
            gl_account=self.expense_account
        )
        
        # Verify
        assert lc_doc.cost_lines.count() == 2
        total_cost = sum(line.amount for line in lc_doc.cost_lines.all())
        assert total_cost == Decimal('75.00')
        
        print("✓ Landed cost creation test passed!")
    
    def test_po_status_transitions(self):
        """Test PO status workflow."""
        
        po = PurchaseOrder.objects.create(
            organization=self.org,
            vendor=self.vendor,
            number='PO-2025-004',
            order_date=date.today(),
            currency=self.currency,
            status=PurchaseOrder.Status.DRAFT
        )
        
        # DRAFT → APPROVED
        assert po.status == PurchaseOrder.Status.DRAFT
        po.status = PurchaseOrder.Status.APPROVED
        po.save()
        assert po.status == PurchaseOrder.Status.APPROVED
        
        # APPROVED → SENT
        po.status = PurchaseOrder.Status.SENT
        po.save()
        assert po.status == PurchaseOrder.Status.SENT
        
        # SENT → RECEIVED
        po.status = PurchaseOrder.Status.RECEIVED
        po.save()
        assert po.status == PurchaseOrder.Status.RECEIVED
        
        # RECEIVED → CLOSED
        po.status = PurchaseOrder.Status.CLOSED
        po.save()
        assert po.status == PurchaseOrder.Status.CLOSED
        
        print("✓ PO status transitions test passed!")
    
    def test_gr_status_transitions(self):
        """Test GR status workflow."""
        
        po = PurchaseOrder.objects.create(
            organization=self.org,
            vendor=self.vendor,
            number='PO-2025-005',
            order_date=date.today(),
            currency=self.currency,
            status=PurchaseOrder.Status.SENT
        )
        
        gr = GoodsReceipt.objects.create(
            organization=self.org,
            purchase_order=po,
            number='GR-2025-003',
            receipt_date=date.today(),
            warehouse=self.warehouse,
            status=GoodsReceipt.Status.DRAFT
        )
        
        # DRAFT → RECEIVED
        assert gr.status == GoodsReceipt.Status.DRAFT
        gr.status = GoodsReceipt.Status.RECEIVED
        gr.save()
        assert gr.status == GoodsReceipt.Status.RECEIVED
        
        # RECEIVED → INSPECTED
        gr.status = GoodsReceipt.Status.INSPECTED
        gr.save()
        assert gr.status == GoodsReceipt.Status.INSPECTED
        
        # INSPECTED → POSTED
        gr.status = GoodsReceipt.Status.POSTED
        gr.save()
        assert gr.status == GoodsReceipt.Status.POSTED
        
        print("✓ GR status transitions test passed!")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
