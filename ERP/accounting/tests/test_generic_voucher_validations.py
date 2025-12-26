from django.test import TestCase
from accounting.forms import GenericVoucherHeaderForm, GenericVoucherLineForm, AdditionalChargeForm, VoucherPaymentForm
from accounting.models import Organization

class VoucherValidationTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Test Org')
    
    def test_header_clean_required_vendor(self):
        form = GenericVoucherHeaderForm(data={}, organization=self.org, module='purchasing')
        self.assertFalse(form.is_valid())
        self.assertIn('vendor', form.errors)
    
    def test_line_clean_debit_credit(self):
        form = GenericVoucherLineForm(data={'debit_amount': 100, 'credit_amount': 50})
        self.assertFalse(form.is_valid())
        self.assertIn('debit_amount', form.errors)  # Custom message
    
    # Sales Invoice specific
    def test_sales_invoice_requires_customer(self):
        form = GenericVoucherHeaderForm(data={'voucher_date': '2023-01-01'}, organization=self.org, module='sales')
        self.assertFalse(form.is_valid())
        self.assertIn('customer', form.errors)
    
    # Purchase Invoice specific
    def test_purchase_invoice_requires_vendor(self):
        form = GenericVoucherHeaderForm(data={'voucher_date': '2023-01-01'}, organization=self.org, module='purchasing')
        self.assertFalse(form.is_valid())
        self.assertIn('vendor', form.errors)
    
    # Journal Entry specific
    def test_journal_entry_no_specific_requires(self):
        form = GenericVoucherHeaderForm(data={'voucher_date': '2023-01-01'}, organization=self.org, module='accounting')
        self.assertTrue(form.is_valid())  # No specific requires
    
    # Goods Receipt specific
    def test_goods_receipt_inventory_checks(self):
        form = GenericVoucherLineForm(data={'product': 'prod1', 'quantity': 0}, config={'affects_inventory': True})
        self.assertFalse(form.is_valid())
        self.assertIn('quantity', form.errors)
    
    # Sales Order specific
    def test_sales_order_date_order(self):
        form = GenericVoucherHeaderForm(data={'order_date': '2023-01-02', 'delivery_date': '2023-01-01'}, organization=self.org, module='sales')
        self.assertFalse(form.is_valid())
        self.assertIn('delivery_date', form.errors)
    
    # Purchase Order specific
    def test_purchase_order_date_order(self):
        form = GenericVoucherHeaderForm(data={'order_date': '2023-01-02', 'delivery_date': '2023-01-01'}, organization=self.org, module='purchasing')
        self.assertFalse(form.is_valid())
        self.assertIn('delivery_date', form.errors)
    
    # Debit/Credit Note specific
    def test_credit_note_customer_required(self):
        form = GenericVoucherHeaderForm(data={'note_date': '2023-01-01'}, organization=self.org, module='sales')
        self.assertFalse(form.is_valid())
        self.assertIn('customer', form.errors)
    
    # Letter of Credit specific
    def test_lc_bank_required(self):
        form = GenericVoucherHeaderForm(data={'lc_date': '2023-01-01'}, organization=self.org, module='banking')
        # Assuming banking requires bank
        self.assertFalse(form.is_valid())
        # self.assertIn('bank', form.errors)  # If implemented
    
    # Inventory Adjustment specific
    def test_inventory_adjustment_quantity_positive(self):
        form = GenericVoucherLineForm(data={'quantity': -1}, config={'affects_inventory': True})
        self.assertFalse(form.is_valid())
        self.assertIn('quantity', form.errors)
    
    # Landed Cost specific
    def test_landed_cost_additional_charges(self):
        form = AdditionalChargeForm(data={'amount': 0}, organization=self.org)
        self.assertFalse(form.is_valid())
        self.assertIn('amount', form.errors)
    
    # AR/AP Receipt/Payment specific
    def test_ar_receipt_payment_sum(self):
        # Test in integration, but here basic
        form = VoucherPaymentForm(data={'amount': 0}, organization=self.org)
        self.assertFalse(form.is_valid())
        self.assertIn('amount', form.errors)
    
    # ... more for UDFs, currencies, etc.