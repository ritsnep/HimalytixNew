"""
Tests for Purchase Invoice Calculator and HTMX Views
"""
from decimal import Decimal
from datetime import timedelta
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounting.models import (
    Organization, Vendor, Currency, ChartOfAccount,
    PurchaseInvoice, PurchaseInvoiceLine, TaxCode, AccountType,
    Agent, Pricing, APPayment, APPaymentLine
)
from locations.models import LocationNode
from accounting.services.purchase_calculator import PurchaseCalculator
from accounting.forms import PurchaseInvoiceForm, PurchaseInvoiceLineForm, PurchasePaymentForm
from inventory.models import Product, Unit, Warehouse

User = get_user_model()


class PurchaseCalculatorTestCase(TestCase):
    """Test PurchaseCalculator service with various scenarios"""

    def setUp(self):
        """Set up test data"""
        self.calc = PurchaseCalculator(lines=[])

    def test_simple_calculation_no_discount_no_vat(self):
        """Test basic calculation: qty * rate = amount"""
        lines = [
            {
                "qty": 10,
                "rate": 100,
                "vat_applicable": False,
                "row_discount_value": 0,
                "row_discount_type": "amount",
            }
        ]
        calc = PurchaseCalculator(lines=lines)
        result = calc.compute()

        self.assertEqual(result["totals"]["subtotal"], Decimal("1000.00"))
        self.assertEqual(result["totals"]["vat_amount"], Decimal("0.00"))
        self.assertEqual(result["totals"]["grand_total"], Decimal("1000.00"))

    def test_calculation_with_percentage_discount(self):
        """Test calculation with row-level percentage discount"""
        lines = [
            {
                "qty": 10,
                "rate": 100,
                "vat_applicable": True,
                "row_discount_value": 10,  # 10%
                "row_discount_type": "percent",
            }
        ]
        calc = PurchaseCalculator(lines=lines)
        result = calc.compute()

        # Gross: 10 * 100 = 1000
        # Discount: 1000 * 10% = 100
        # Net: 1000 - 100 = 900
        # VAT: 900 * 13% = 117
        self.assertEqual(result["totals"]["subtotal"], Decimal("1000.00"))
        self.assertEqual(result["rows"][0]["row_discount"], Decimal("100.00"))
        self.assertEqual(result["rows"][0]["net"], Decimal("900.00"))

    def test_calculation_with_vat(self):
        """Test VAT calculation at 13%"""
        lines = [
            {
                "qty": 100,
                "rate": 50,
                "vat_applicable": True,
                "row_discount_value": 0,
                "row_discount_type": "amount",
            }
        ]
        calc = PurchaseCalculator(lines=lines)
        result = calc.compute()

        # Gross: 100 * 50 = 5000
        # No discount
        # Net: 5000
        # VAT: 5000 * 13% = 650
        self.assertEqual(result["totals"]["subtotal"], Decimal("5000.00"))
        self.assertEqual(result["totals"]["total_after_header"], Decimal("5000.00"))
        self.assertEqual(result["totals"]["vat_amount"], Decimal("650.00"))
        self.assertEqual(result["totals"]["grand_total"], Decimal("5650.00"))

    def test_mixed_vatable_and_nonvatable_items(self):
        """Test mixed items with different VAT applicability"""
        lines = [
            {
                "qty": 10,
                "rate": 100,
                "vat_applicable": True,
                "row_discount_value": 0,
                "row_discount_type": "amount",
            },
            {
                "qty": 5,
                "rate": 200,
                "vat_applicable": False,  # No VAT
                "row_discount_value": 0,
                "row_discount_type": "amount",
            },
        ]
        calc = PurchaseCalculator(lines=lines)
        result = calc.compute()

        # Vatable: 10 * 100 = 1000, VAT = 130
        # NonVatable: 5 * 200 = 1000, VAT = 0
        # Total: 2000 + 130 = 2130
        self.assertEqual(result["totals"]["subtotal"], Decimal("2000.00"))
        self.assertEqual(result["totals"]["vat_amount"], Decimal("130.00"))
        self.assertEqual(result["totals"]["grand_total"], Decimal("2130.00"))

    def test_header_discount_amount(self):
        """Test header-level discount as fixed amount"""
        lines = [
            {
                "qty": 100,
                "rate": 100,
                "vat_applicable": True,
                "row_discount_value": 0,
                "row_discount_type": "amount",
            }
        ]
        calc = PurchaseCalculator(
            lines=lines,
            header_discount_value=500,
            header_discount_type="amount",
        )
        result = calc.compute()

        # Gross: 100 * 100 = 10000
        # Header discount: 500
        # Net: 10000 - 500 = 9500
        # VAT: 9500 * 13% = 1235
        self.assertEqual(result["totals"]["subtotal"], Decimal("10000.00"))
        self.assertEqual(result["totals"]["header_discount"], Decimal("500.00"))
        # VAT should be applied to amount after discount
        self.assertEqual(result["totals"]["vat_amount"], Decimal("1235.00"))

    def test_header_discount_percentage(self):
        """Test header-level discount as percentage"""
        lines = [
            {
                "qty": 100,
                "rate": 100,
                "vat_applicable": True,
                "row_discount_value": 0,
                "row_discount_type": "amount",
            }
        ]
        calc = PurchaseCalculator(
            lines=lines,
            header_discount_value=10,  # 10%
            header_discount_type="percent",
        )
        result = calc.compute()

        # Gross: 10000
        # Header discount: 10000 * 10% = 1000
        # Net: 9000
        # VAT: 9000 * 13% = 1170
        self.assertEqual(result["totals"]["subtotal"], Decimal("10000.00"))
        self.assertEqual(result["totals"]["header_discount"], Decimal("1000.00"))
        self.assertEqual(result["totals"]["vat_amount"], Decimal("1170.00"))

    def test_bill_rounding(self):
        """Test bill rounding adjustment"""
        lines = [
            {
                "qty": 3,
                "rate": 33.33,
                "vat_applicable": True,
                "row_discount_value": 0,
                "row_discount_type": "amount",
            }
        ]
        calc = PurchaseCalculator(lines=lines, bill_rounding=Decimal("0.05"))
        result = calc.compute()

        # Should add 0.05 to grand total
        self.assertEqual(result["totals"]["rounding"], Decimal("0.05"))
        self.assertGreater(result["totals"]["grand_total"], Decimal("100.00"))

    def test_zero_items(self):
        """Test calculation with no items"""
        calc = PurchaseCalculator(lines=[])
        result = calc.compute()

        self.assertEqual(result["totals"]["subtotal"], Decimal("0.00"))
        self.assertEqual(result["totals"]["grand_total"], Decimal("0.00"))

    def test_multiple_items_with_various_discounts(self):
        """Test complex scenario: multiple items with various discounts"""
        lines = [
            {
                "qty": 10,
                "rate": 500,
                "vat_applicable": True,
                "row_discount_value": 5,  # 5%
                "row_discount_type": "percent",
            },
            {
                "qty": 20,
                "rate": 100,
                "vat_applicable": True,
                "row_discount_value": 50,  # Fixed amount
                "row_discount_type": "amount",
            },
            {
                "qty": 5,
                "rate": 1000,
                "vat_applicable": False,
                "row_discount_value": 0,
                "row_discount_type": "amount",
            },
        ]
        calc = PurchaseCalculator(
            lines=lines,
            header_discount_value=2,
            header_discount_type="percent",
        )
        result = calc.compute()

        # Item 1: 10*500=5000, discount 5%=250, net=4750, vatable
        # Item 2: 20*100=2000, discount=50, net=1950, vatable
        # Item 3: 5*1000=5000, discount=0, net=5000, non-vatable
        # Gross: 12000
        # Row discounts: 250+50 = 300
        # Subtotal: 11700
        # Header discount 2%: 234
        # Vatable total: 4750+1950-portion of header discount
        # Non-vatable total: 5000-portion of header discount
        self.assertGreater(result["totals"]["subtotal"], Decimal("10000.00"))
        self.assertGreater(result["totals"]["vat_amount"], Decimal("0.00"))


class PurchaseInvoiceFormTestCase(TestCase):
    """Test PurchaseInvoice forms"""

    def setUp(self):
        """Set up test data"""
        self.organization = Organization.objects.create(
            name="Test Org",
            code="TEST",
        )
        # Ensure vendor has an accounts payable account (non-null constraint)
        self.liability_type = AccountType.objects.create(name="Liability", nature="liability", display_order=2)
        self.expense_type = AccountType.objects.create(name="Expense", nature="expense", display_order=3)
        self.ap_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_code="2001",
            account_name="Accounts Payable",
            account_type=self.liability_type,
        )
        self.purchase_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_code="5001",
            account_name="Purchase Expense",
            account_type=self.expense_type,
        )
        self.vendor = Vendor.objects.create(
            organization=self.organization,
            code="V001",
            display_name="Test Vendor",
            accounts_payable_account=self.ap_account,
        )
        # Currency model uses currency_code/currency_name fields
        self.currency = Currency.objects.create(
            currency_code="USD",
            currency_name="US Dollar",
        )

    def test_purchase_invoice_form_valid(self):
        """Test valid purchase invoice form"""
        data = {
            "organization": self.organization.id,
            "vendor": self.vendor.vendor_id,
            "invoice_number": "PI001",
            "invoice_date": timezone.now().date(),
            "due_date": timezone.now().date(),
            "currency": self.currency.currency_code,
            "purchase_account": self.purchase_account.account_id,
            "exchange_rate": 1.0,
        }
        form = PurchaseInvoiceForm(data=data, organization=self.organization)
        self.assertTrue(form.is_valid(), form.errors.as_text())

    def test_purchase_invoice_form_requires_vendor(self):
        """Test that vendor is required"""
        data = {
            "organization": self.organization.id,
            "invoice_number": "PI001",
            "invoice_date": timezone.now().date(),
            "currency": self.currency.currency_code,
            "purchase_account": self.purchase_account.account_id,
        }
        form = PurchaseInvoiceForm(data=data, organization=self.organization)
        self.assertFalse(form.is_valid())
        self.assertIn("vendor", form.errors)

    def test_purchase_invoice_form_requires_currency_and_purchase_account(self):
        """Ensure currency and purchase account are validated"""
        data = {
            "organization": self.organization.id,
            "vendor": self.vendor.vendor_id,
            "invoice_number": "PI002",
            "invoice_date": timezone.now().date(),
        }
        form = PurchaseInvoiceForm(data=data, organization=self.organization)
        self.assertFalse(form.is_valid())
        self.assertIn("currency", form.errors)
        self.assertIn("purchase_account", form.errors)

    def test_purchase_invoice_form_due_date_not_before_invoice_date(self):
        """Due date cannot be earlier than invoice date"""
        invoice_date = timezone.now().date()
        due_date = invoice_date - timedelta(days=1)
        data = {
            "organization": self.organization.id,
            "vendor": self.vendor.vendor_id,
            "invoice_number": "PI003",
            "invoice_date": invoice_date,
            "due_date": due_date,
            "currency": self.currency.currency_code,
            "purchase_account": self.purchase_account.account_id,
            "exchange_rate": 1,
        }
        form = PurchaseInvoiceForm(data=data, organization=self.organization)
        self.assertFalse(form.is_valid())
        self.assertIn("due_date", form.errors)


class PurchaseInvoiceLineFormTestCase(TestCase):
    """Test validations on the invoice line form"""

    def setUp(self):
        self.organization = Organization.objects.create(name="Line Org", code="LINE")
        self.account_type = AccountType.objects.create(name="Expense", nature="expense", display_order=5)
        self.account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_code="5100",
            account_name="Purchase Expense",
            account_type=self.account_type,
        )
        self.product = Product.objects.create(
            organization=self.organization,
            code="PRD001",
            name="Inventory Item",
            is_inventory_item=True,
        )
        self.warehouse = Warehouse.objects.create(
            organization=self.organization,
            code="WH1",
            name="Main Warehouse",
            is_active=True,
        )

    def _base_data(self):
        return {
            "quantity": 1,
            "unit_cost": 100,
            "account": self.account.account_id,
        }

    def test_line_form_requires_description_or_product(self):
        data = self._base_data()
        form = PurchaseInvoiceLineForm(data=data, organization=self.organization)
        self.assertFalse(form.is_valid())
        self.assertIn("__all__", form.errors)

    def test_line_form_discount_not_exceed_line_amount(self):
        data = self._base_data()
        data.update({
            "product": self.product.id,
            "discount_amount": 250,
            "description": "Line",
            "warehouse": self.warehouse.id,
        })
        form = PurchaseInvoiceLineForm(data=data, organization=self.organization)
        self.assertFalse(form.is_valid())
        self.assertIn("discount_amount", form.errors)

    def test_line_form_requires_warehouse_for_inventory_product(self):
        data = self._base_data()
        data.update({
            "product": self.product.id,
            "description": "Inventory",
        })
        form = PurchaseInvoiceLineForm(data=data, organization=self.organization)
        self.assertFalse(form.is_valid())
        self.assertIn("warehouse", form.errors)

    def test_line_form_vat_rate_range(self):
        data = self._base_data()
        data.update({
            "product": self.product.id,
            "description": "VAT Test",
            "warehouse": self.warehouse.id,
            "vat_rate": 150,
        })
        form = PurchaseInvoiceLineForm(data=data, organization=self.organization)
        self.assertFalse(form.is_valid())
        self.assertIn("vat_rate", form.errors)


class PurchasePaymentFormTestCase(TestCase):
    """Test validations on the payment form"""

    def setUp(self):
        self.invoice_date = timezone.now().date()
        self.cash_bank_choices = [('', 'Select account'), ('1', 'Main Cash')]

    def test_payment_form_allows_blank_amount(self):
        form = PurchasePaymentForm(
            data={
                'payment_method': 'cash',
            },
            invoice_date=self.invoice_date,
            cash_bank_choices=self.cash_bank_choices,
        )
        self.assertTrue(form.is_valid())

    def test_payment_form_rejects_negative_amount(self):
        form = PurchasePaymentForm(
            data={
                'payment_method': 'cash',
                'amount': '-10',
            },
            invoice_date=self.invoice_date,
            cash_bank_choices=self.cash_bank_choices,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('amount', form.errors)

    def test_payment_form_requires_bank_account_for_bank_methods(self):
        form = PurchasePaymentForm(
            data={
                'payment_method': 'bank',
                'amount': '100',
            },
            invoice_date=self.invoice_date,
            cash_bank_choices=self.cash_bank_choices,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('cash_bank_id', form.errors)

    def test_payment_form_due_date_not_before_invoice(self):
        due_date = self.invoice_date - timedelta(days=1)
        form = PurchasePaymentForm(
            data={
                'payment_method': 'cash',
                'amount': '50',
                'cash_bank_id': '1',
                'due_date': due_date,
            },
            invoice_date=self.invoice_date,
            cash_bank_choices=self.cash_bank_choices,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('due_date', form.errors)


class PurchaseInvoiceHTMXViewsTestCase(TestCase):
    """Test HTMX endpoints for purchase invoice form"""

    def setUp(self):
        """Set up test client and user"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123",
        )
        self.organization = Organization.objects.create(
            name="Test Org",
            code="TEST",
        )
        self.user.organization = self.organization
        self.user.save()

    def test_purchase_recalc_endpoint_with_valid_data(self):
        """Test recalc endpoint with valid form data"""
        self.client.login(username="testuser", password="testpass123")

        # Post data for form
        data = {
            "organization": self.organization.id,
            "vendor": "",  # Will be valid for recalc
            "invoice_date": timezone.now().date(),
            "currency": "",
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-0-qty": "10",
            "items-0-rate": "100",
            "items-0-vat_applicable": "on",
            "payments-TOTAL_FORMS": "0",
            "payments-INITIAL_FORMS": "0",
            "discount_value": "0",
            "discount_type": "%",
        }

        response = self.client.post(
            "/accounting/purchase/recalc/",
            data=data,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        # Should return 200 and contain HTML fragment
        self.assertEqual(response.status_code, 200)
        self.assertIn("Grand Total".encode(), response.content)

    def test_purchase_line_add_endpoint(self):
        """Test add line endpoint"""
        self.client.login(username="testuser", password="testpass123")

        data = {
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
        }

        response = self.client.post(
            "/accounting/purchase/add-line/",
            data=data,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        # Should return 200 and contain new row HTML
        self.assertEqual(response.status_code, 200)


# Integration test example (simplified)
class PurchaseInvoiceIntegrationTestCase(TestCase):
    """Integration tests for complete purchase invoice workflow"""

    def setUp(self):
        """Set up test data"""
        self.organization = Organization.objects.create(
            name="Test Org", code="TEST"
        )
        self.currency = Currency.objects.create(
            currency_code="USD", currency_name="US Dollar"
        )
        # Create account type first
        self.expense_account_type = AccountType.objects.create(
            name="Expense", nature="expense", display_order=5
        )
        self.asset_account_type = AccountType.objects.create(
            name="Asset", nature="asset", display_order=1
        )
        self.account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_code="5001",
            account_name="Purchases",
            account_type=self.expense_account_type,
        )
        self.vendor = Vendor.objects.create(
            organization=self.organization, code="V001", display_name="Test Vendor",
            accounts_payable_account=self.account
        )
        # Create a bank account for payments
        self.bank_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_code="1020",
            account_name="Bank of Test",
            account_type=self.asset_account_type,
            is_bank_account=True,
        )

    def test_full_purchase_invoice_calculation_workflow(self):
        """Test a complete purchase invoice calculation"""
        # Simulate form data
        form_data = {
            "organization": self.organization.id,
            "vendor": self.vendor.vendor_id,
            "invoice_number": "PI001",
            "invoice_date": timezone.now().date(),
            "currency": self.currency.currency_code,
            "discount_value": 0,
            "discount_type": "%",
            "bill_rounding": 0,
        }

        items_data = [
            {
                "description": "Item 1",
                "product_code": "P001",
                "quantity": 10,
                "unit_cost": 100,
                "discount_amount": 0,
                "account": self.account.account_id,
                "vat_applicable": True,
            },
            {
                "description": "Item 2",
                "product_code": "P002",
                "quantity": 5,
                "unit_cost": 200,
                "discount_amount": 0,
                "account": self.account.account_id,
                "vat_applicable": False,
            },
        ]

        # Create calculator
        self.calc_lines = [
            {
                "qty": item["quantity"],
                "rate": item["unit_cost"],
                "vat_applicable": item.get("vat_applicable", True),
                "row_discount_value": item.get("discount_amount", 0),
                "row_discount_type": "amount",
            }
            for item in items_data
        ]

    def test_create_purchase_invoice_with_lines_and_payments(self):
        """Integration test: create a purchase invoice with line items and payments"""
        client = Client()
        user = User.objects.create_user(username='user_create', password='pw')
        user.organization = self.organization
        user.save()
        client.login(username='user_create', password='pw')

        data = {
            'organization': self.organization.id,
            'vendor': self.vendor.vendor_id,
            'invoice_number': 'PI200',
            'invoice_date': timezone.now().date(),
            'currency': self.currency.currency_code,
            'exchange_rate': '1',
            'purchase_account': self.account.account_id,
            # Line items formset
            'items-TOTAL_FORMS': '2',
            'items-INITIAL_FORMS': '0',
            'items-0-description': 'Item A',
            'items-0-product': '',
            'items-0-quantity': '2',
            'items-0-unit_cost': '100',
            'items-0-account': self.account.account_id,
            'items-1-description': 'Item B',
            'items-1-product': '',
            'items-1-quantity': '1',
            'items-1-unit_cost': '200',
            'items-1-account': self.account.account_id,
            # Payments formset
            'payments-TOTAL_FORMS': '1',
            'payments-INITIAL_FORMS': '0',
            'payments-0-payment_method': 'bank',
            'payments-0-cash_bank_id': str(self.bank_account.account_id),
            'payments-0-due_date': timezone.now().date(),
            'payments-0-amount': '200',
        }

        response = client.post(
            '/accounting/purchase-invoice/new-enhanced/',
            data,
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Purchase Invoice created successfully', response.content)

        inv = PurchaseInvoice.objects.latest("id")
        self.assertEqual(inv.vendor, self.vendor)
        lines = PurchaseInvoiceLine.objects.filter(invoice=inv)
        self.assertEqual(lines.count(), 2)
        payments = APPayment.objects.filter(vendor=self.vendor, organization=self.organization)
        # Our handler creates a payment and links it to the invoice
        self.assertTrue(payments.exists())
        ap = payments.first()
        self.assertEqual(ap.amount, Decimal('200'))
        alines = ap.lines.filter(invoice=inv)
        self.assertTrue(alines.exists())

        calc = PurchaseCalculator(lines=self.calc_lines)
        result = calc.compute()

        # Verify calculations
        # Item 1: 10 * 100 = 1000, vatable
        # Item 2: 5 * 200 = 1000, non-vatable
        # Total: 2000
        # VAT: 1000 * 13% = 130 (only on item 1)
        # Grand total: 2130

        self.assertEqual(result["totals"]["subtotal"], Decimal("2000.00"))
        self.assertEqual(result["totals"]["vat_amount"], Decimal("130.00"))
        self.assertEqual(result["totals"]["grand_total"], Decimal("2130.00"))

    def test_purchase_invoice_save_invalid_returns_422(self):
        client = Client()
        user = User.objects.create_user(username='user_invalid', password='pw')
        user.organization = self.organization
        user.save()
        client.login(username='user_invalid', password='pw')

        response = client.post(
            '/accounting/purchase-invoice/new-enhanced/',
            {
                'organization': self.organization.id,
                'invoice_date': timezone.now().date(),
                'currency': self.currency.currency_code,
                'items-TOTAL_FORMS': '1',
                'items-INITIAL_FORMS': '0',
                'payments-TOTAL_FORMS': '0',
                'payments-INITIAL_FORMS': '0',
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn(b'Please correct the errors', response.content)


class PurchaseInvoiceEnhancedEndpointsTestCase(TestCase):
    """Tests for enhanced purchase invoice endpoints."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='enh_user', password='pw')
        self.organization = Organization.objects.create(name="Enhanced Org", code="ENH")
        self.user.organization = self.organization
        self.user.save()
        self.client.force_login(self.user)

        self.currency = Currency.objects.create(
            currency_code="USD",
            currency_name="US Dollar",
            symbol="$",
            is_active=True,
        )
        # Ensure vendor has required accounts_payable_account
        self.ap_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_code="2002",
            account_name="Accounts Payable - ENH",
            account_type=AccountType.objects.create(name="Liability", nature="liability", display_order=3),
        )
        self.vendor = Vendor.objects.create(
            organization=self.organization,
            code="V100",
            display_name="Vendor X",
            accounts_payable_account=self.ap_account,
        )
        self.location_area = LocationNode.objects.create(
            id="AREA001",
            type=LocationNode.Type.AREA,
            name_en="Test Area",
            is_active=True,
        )
        self.agent = Agent.objects.create(
            organization=self.organization,
            code="A1",
            name="Agent One",
            area=self.location_area,
        )
        # Assign agent and area to vendor
        self.vendor.agent = self.agent
        self.vendor.area = self.location_area
        self.vendor.save()
        self.unit = Unit.objects.create(
            organization=self.organization,
            code="PCS",
            name="Pieces",
        )
        self.product = Product.objects.create(
            organization=self.organization,
            code="P001",
            name="Widget",
            base_unit=self.unit,
            cost_price=Decimal("50.00"),
        )
        Pricing.objects.create(
            organization=self.organization,
            product=self.product,
            party=self.vendor,
            price_type="special",
            unit_price=Decimal("75.00"),
            discount_type="percentage",
            discount_value=Decimal("0.00"),
            currency=self.currency,
            effective_from=timezone.now().date(),
            is_active=True,
            priority=1,
        )

    def test_load_vendor_details_returns_agent_area(self):
        response = self.client.get(
            f"/accounting/purchase-invoice/load-vendor/{self.vendor.vendor_id}/"
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        print('DEBUG load_vendor payload:', payload)
        self.assertTrue(payload.get("success"), msg=str(payload))
        # We expect some agent/area to be selected; exact selection is implementation-dependent
        self.assertTrue(payload.get("agent_id") is not None, msg=str(payload))
        self.assertTrue(payload.get("area_id") is not None, msg=str(payload))

    def test_load_product_details_uses_party_price(self):
        response = self.client.get(
            f"/accounting/purchase-invoice/load-product/{self.product.id}/",
            {"vendor_id": self.vendor.vendor_id},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get("success"))
        self.assertEqual(payload.get("code"), self.product.code)
        self.assertEqual(payload.get("unit"), self.unit.name)
        self.assertEqual(Decimal(str(payload.get("rate"))), Decimal("75.00"))
