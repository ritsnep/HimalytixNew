"""
Tests for Multi-Currency Support in the ERP System

This test module verifies:
1. Foreign currency invoice posting uses converted (functional) amounts in GL
2. Currency exchange rate lookup and application
3. JournalLine multi-currency fields (txn_currency, fx_rate, amount_txn, amount_base)
4. SalesInvoice and PurchaseInvoice multi-currency calculations
"""

from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounting.models import (
    Currency,
    CurrencyExchangeRate,
    FiscalYear,
    Journal,
    JournalLine,
    JournalType,
    AccountingPeriod,
    ChartOfAccount,
    AccountType,
    GeneralLedger,
    SalesInvoice,
    SalesInvoiceLine,
    PurchaseInvoice,
    PurchaseInvoiceLine,
    Customer,
    Vendor,
    PaymentTerm,
)
from accounting.services.currency_service import resolvecurrency
from usermanagement.models import Organization

User = get_user_model()


class MultiCurrencyTestCase(TestCase):
    """Base test case with common multi-currency test setup"""

    @classmethod
    def setUpTestData(cls):
        """Create common test data for all multi-currency test"""
        # Create or get currencies first
        cls.npr, _ = Currency.objects.get_or_create(
            currency_code='NPR',
            defaults={
                'currency_name': 'Nepalese Rupee',
                'symbol': 'Rs.',
                'is_active': True
            }
        )
        cls.usd, _ = Currency.objects.get_or_create(
            currency_code='USD',
            defaults={
                'currency_name': 'US Dollar',
                'symbol': '$',
                'is_active': True
            }
        )

        # Create user
        cls.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        # Create organization with NPR as base currency
        cls.organization = Organization.objects.create(
            name='Test Org',
            code='TEST',
            type='test',
            base_currency_code=cls.npr  # Use the Currency instance
        )
        cls.user.organization = cls.organization
        cls.user.save()
        cls.eur, _ = Currency.objects.get_or_create(
            currency_code='EUR',
            defaults={
                'currency_name': 'Euro',
                'symbol': '€',
                'is_active': True
            }
        )

        # Create exchange rates (NPR is base)
        today = date.today()
        CurrencyExchangeRate.objects.create(
            organization=cls.organization,
            from_currency=cls.npr,
            to_currency=cls.usd,
            rate_date=today,
            exchange_rate=Decimal('0.0075'),  # 1 NPR = 0.0075 USD
            source='test',
            is_active=True,
            created_by=cls.user
        )
        # For USD to NPR: 1 USD = 133.33 NPR (inverse of 0.0075)
        CurrencyExchangeRate.objects.create(
            organization=cls.organization,
            from_currency=cls.usd,
            to_currency=cls.npr,
            rate_date=today,
            exchange_rate=Decimal('133.333333'),
            source='test',
            is_active=True,
            created_by=cls.user
        )

        # Create account types
        cls.asset_type = AccountType.objects.create(
            name='Assets',
            nature='debit',
            code='ASSET'
        )
        cls.revenue_type = AccountType.objects.create(
            name='Revenue',
            nature='credit',
            code='REVENUE'
        )
        cls.expense_type = AccountType.objects.create(
            name='Expense',
            nature='debit',
            code='EXPENSE'
        )
        cls.liability_type = AccountType.objects.create(
            name='Liability',
            nature='credit',
            code='LIABILITY'
        )

        # Create chart of accounts
        cls.cash_account = ChartOfAccount.objects.create(
            organization=cls.organization,
            account_code='1000',
            account_name='Cash',
            account_type=cls.asset_type,
            is_active=True
        )
        cls.ar_account = ChartOfAccount.objects.create(
            organization=cls.organization,
            account_code='1100',
            account_name='Accounts Receivable',
            account_type=cls.asset_type,
            is_active=True
        )
        cls.revenue_account = ChartOfAccount.objects.create(
            organization=cls.organization,
            account_code='4000',
            account_name='Sales Revenue',
            account_type=cls.revenue_type,
            is_active=True
        )
        cls.ap_account = ChartOfAccount.objects.create(
            organization=cls.organization,
            account_code='2000',
            account_name='Accounts Payable',
            account_type=cls.liability_type,
            is_active=True
        )
        cls.expense_account = ChartOfAccount.objects.create(
            organization=cls.organization,
            account_code='5000',
            account_name='Purchase Expense',
            account_type=cls.expense_type,
            is_active=True
        )

        # Create fiscal year
        cls.fiscal_year = FiscalYear.objects.create(
            organization=cls.organization,
            code='2024',
            name='Fiscal Year 2024',
            start_date=date.today() - timedelta(days=365),
            end_date=date.today() + timedelta(days=365),
            status='open',
            is_current=True,
            created_by=cls.user
        )

        # Create accounting period
        cls.period = AccountingPeriod.objects.create(
            fiscal_year=cls.fiscal_year,
            organization=cls.organization,
            period_number=1,
            name='Test Period',
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=30),
            status='open'
        )

        # Create journal type
        cls.journal_type = JournalType.objects.create(
            organization=cls.organization,
            code='GL',
            name='General Journal',
            is_active=True
        )

        # Create customer and vendor
        cls.customer = Customer.objects.create(
            organization=cls.organization,
            customer_name='Test Customer',
            accounts_receivable_account=cls.ar_account,
            created_by=cls.user
        )
        cls.vendor = Vendor.objects.create(
            organization=cls.organization,
            display_name='Test Vendor',
            accounts_payable_account=cls.ap_account,
            created_by=cls.user
        )

        # Create payment term
        cls.payment_term = PaymentTerm.objects.create(
            organization=cls.organization,
            name='Net 30',
            days=30,
            is_active=True
        )


class JournalMultiCurrencyTests(MultiCurrencyTestCase):
    """Test multi-currency support in Journal entries"""

    def test_journal_with_usd_currency(self):
        """Test that journals can be created with USD currency"""
        journal = Journal.objects.create(
            organization=self.organization,
            journal_type=self.journal_type,
            period=self.period,
            journal_date=date.today(),
            currency_code='USD',
            exchange_rate=Decimal('133.333333'),
            status='draft',
            created_by=self.user
        )
        
        self.assertEqual(journal.currency_code, 'USD')
        self.assertEqual(journal.exchange_rate, Decimal('133.333333'))

    def test_journal_line_multi_currency_fields(self):
        """Test JournalLine has txn_currency, fx_rate, amount_txn, amount_base fields"""
        journal = Journal.objects.create(
            organization=self.organization,
            journal_type=self.journal_type,
            period=self.period,
            journal_date=date.today(),
            currency_code='USD',
            exchange_rate=Decimal('133.333333'),
            status='draft',
            created_by=self.user
        )

        # Create journal line with multi-currency fields
        line = JournalLine.objects.create(
            journal=journal,
            line_number=1,
            account=self.cash_account,
            debit_amount=Decimal('1000.00'),  # Amount in base currency (NPR)
            txn_currency=self.usd,
            fx_rate=Decimal('133.333333'),
            amount_txn=Decimal('7.50'),  # Amount in transaction currency (USD)
            amount_base=Decimal('1000.00')  # Amount in base currency (NPR)
        )

        # Verify all multi-currency fields exist and have correct values
        self.assertEqual(line.txn_currency, self.usd)
        self.assertEqual(line.fx_rate, Decimal('133.333333'))
        self.assertEqual(line.amount_txn, Decimal('7.50'))
        self.assertEqual(line.amount_base, Decimal('1000.00'))

    def test_journal_posting_converts_to_functional_currency(self):
        """Test that posting a foreign currency journal creates GL entries in base currency"""
        # Create a journal in USD
        journal = Journal.objects.create(
            organization=self.organization,
            journal_type=self.journal_type,
            period=self.period,
            journal_date=date.today(),
            currency_code='USD',
            exchange_rate=Decimal('133.333333'),
            status='draft',
            created_by=self.user
        )

        # Add journal lines (1000 USD = 133,333.33 NPR)
        JournalLine.objects.create(
            journal=journal,
            line_number=1,
            account=self.cash_account,
            debit_amount=Decimal('133333.33'),
            credit_amount=Decimal('0'),
            txn_currency=self.usd,
            fx_rate=Decimal('133.333333'),
            amount_txn=Decimal('1000.00'),
            amount_base=Decimal('133333.33')
        )
        JournalLine.objects.create(
            journal=journal,
            line_number=2,
            account=self.revenue_account,
            debit_amount=Decimal('0'),
            credit_amount=Decimal('133333.33'),
            txn_currency=self.usd,
            fx_rate=Decimal('133.333333'),
            amount_txn=Decimal('1000.00'),
            amount_base=Decimal('133333.33')
        )

        # Post the journal
        posting_service = PostingService(self.user)
        posted_journal = posting_service.post(journal)

        # Verify journal was posted
        self.assertEqual(posted_journal.status, 'posted')

        # Verify GL entries were created with base currency amounts
        gl_entries = GeneralLedger.objects.filter(journal=posted_journal)
        self.assertEqual(gl_entries.count(), 2)

        # Check that GL entries use functional (base) currency amounts
        for gl_entry in gl_entries:
            if gl_entry.account == self.cash_account:
                # Debit entry should have functional debit amount
                self.assertGreater(gl_entry.debit_amount, Decimal('0'))
                self.assertEqual(gl_entry.debit_amount, Decimal('133333.33'))
            elif gl_entry.account == self.revenue_account:
                # Credit entry should have functional credit amount
                self.assertGreater(gl_entry.credit_amount, Decimal('0'))
                self.assertEqual(gl_entry.credit_amount, Decimal('133333.33'))


class SalesInvoiceMultiCurrencyTests(MultiCurrencyTestCase):
    """Test multi-currency support in Sales Invoices"""

    def test_sales_invoice_currency_fields(self):
        """Test that SalesInvoice has currency and exchange_rate fields"""
        invoice = SalesInvoice.objects.create(
            organization=self.organization,
            customer=self.customer,
            invoice_number='SI-001',
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            currency=self.usd,
            exchange_rate=Decimal('133.333333'),
            status='draft',
            created_by=self.user
        )

        self.assertEqual(invoice.currency, self.usd)
        self.assertEqual(invoice.exchange_rate, Decimal('133.333333'))

    def test_sales_invoice_base_currency_total_calculation(self):
        """Test that SalesInvoice calculates base_currency_total correctly"""
        # Create invoice in USD
        invoice = SalesInvoice.objects.create(
            organization=self.organization,
            customer=self.customer,
            invoice_number='SI-002',
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            currency=self.usd,
            exchange_rate=Decimal('133.333333'),
            status='draft',
            created_by=self.user
        )

        # Add invoice line for $100 USD
        SalesInvoiceLine.objects.create(
            invoice=invoice,
            line_number=1,
            description='Test Product',
            quantity=Decimal('1.0'),
            unit_price=Decimal('100.00'),
            revenue_account=self.revenue_account,
            created_by=self.user
        )

        # Recompute totals
        invoice.recompute_totals(save=True)

        # Verify calculations
        self.assertEqual(invoice.total, Decimal('100.00'))  # USD amount
        # base_currency_total = total * exchange_rate
        expected_base_total = Decimal('100.00') * Decimal('133.333333')
        self.assertAlmostEqual(
            invoice.base_currency_total,
            expected_base_total,
            places=2
        )

    def test_sales_invoice_posting_creates_base_currency_gl(self):
        """Test that posting a foreign currency invoice creates GL entries in base currency"""
        service = SalesInvoiceService(self.user)

        # Create invoice in USD
        invoice = service.create_invoice(
            organization=self.organization,
            customer=self.customer,
            invoice_date=date.today(),
            currency=self.usd,
            exchange_rate=Decimal('133.333333'),
            lines=[
                {
                    'description': 'Test Service',
                    'quantity': Decimal('1.0'),
                    'unit_price': Decimal('100.00'),
                    'revenue_account': self.revenue_account,
                }
            ],
            payment_term=self.payment_term
        )

        # Validate and post invoice
        invoice = service.validate_invoice(invoice)
        posted_invoice = service.post_invoice(
            invoice,
            journal_type=self.journal_type
        )

        # Verify journal was created and posted
        self.assertIsNotNone(posted_invoice.journal)
        journal = posted_invoice.journal
        self.assertEqual(journal.status, 'posted')

        # Verify GL entries use base currency amounts
        gl_entries = GeneralLedger.objects.filter(journal=journal)
        self.assertGreater(gl_entries.count(), 0)

        # The GL entries should be in NPR (base currency)
        for gl_entry in gl_entries:
            # Check that amounts are converted to base currency
            total_amount = gl_entry.debit_amount + gl_entry.credit_amount
            if total_amount > 0:
                # Should be around 13,333.33 NPR (100 USD * 133.333333)
                self.assertGreater(total_amount, Decimal('10000'))


class PurchaseInvoiceMultiCurrencyTests(MultiCurrencyTestCase):
    """Test multi-currency support in Purchase Invoices"""

    def test_purchase_invoice_currency_fields(self):
        """Test that PurchaseInvoice has currency and exchange_rate fields"""
        invoice = PurchaseInvoice.objects.create(
            organization=self.organization,
            vendor=self.vendor,
            invoice_number='PI-001',
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            currency=self.usd,
            exchange_rate=Decimal('133.333333'),
            status='draft',
            created_by=self.user
        )

        self.assertEqual(invoice.currency, self.usd)
        self.assertEqual(invoice.exchange_rate, Decimal('133.333333'))

    def test_purchase_invoice_base_currency_total_calculation(self):
        """Test that PurchaseInvoice calculates base_currency_total correctly"""
        # Create invoice in USD
        invoice = PurchaseInvoice.objects.create(
            organization=self.organization,
            vendor=self.vendor,
            invoice_number='PI-002',
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            currency=self.usd,
            exchange_rate=Decimal('133.333333'),
            status='draft',
            created_by=self.user
        )

        # Add invoice line for $150 USD
        PurchaseInvoiceLine.objects.create(
            invoice=invoice,
            line_number=1,
            description='Test Material',
            quantity=Decimal('1.0'),
            unit_cost=Decimal('150.00'),
            account=self.expense_account,
            created_by=self.user
        )

        # Recompute totals
        invoice.recompute_totals(save=True)

        # Verify calculations
        self.assertEqual(invoice.total, Decimal('150.00'))  # USD amount
        # base_currency_total = total * exchange_rate
        expected_base_total = Decimal('150.00') * Decimal('133.333333')
        self.assertAlmostEqual(
            invoice.base_currency_total,
            expected_base_total,
            places=2
        )


class CurrencyExchangeRateTests(MultiCurrencyTestCase):
    """Test currency exchange rate functionality"""

    def test_exchange_rate_lookup(self):
        """Test that exchange rates can be looked up correctly"""
        today = date.today()
        rate = CurrencyExchangeRate.objects.filter(
            organization=self.organization,
            from_currency=self.usd,
            to_currency=self.npr,
            rate_date__lte=today,
            is_active=True
        ).order_by('-rate_date').first()

        self.assertIsNotNone(rate)
        self.assertEqual(rate.exchange_rate, Decimal('133.333333'))

    def test_multiple_currency_rates(self):
        """Test that multiple currency rates can exist"""
        # Verify we have rates for different currency pairs
        usd_to_npr = CurrencyExchangeRate.objects.filter(
            organization=self.organization,
            from_currency=self.usd,
            to_currency=self.npr
        ).exists()
        
        npr_to_usd = CurrencyExchangeRate.objects.filter(
            organization=self.organization,
            from_currency=self.npr,
            to_currency=self.usd
        ).exists()

        self.assertTrue(usd_to_npr)
        self.assertTrue(npr_to_usd)

    def test_exchange_rate_admin_exists(self):
        """Test that CurrencyExchangeRate is registered in admin"""
        from django.contrib import admin
        from accounting.models import CurrencyExchangeRate

        self.assertTrue(admin.site.is_registered(CurrencyExchangeRate))


class DeprecatedFieldsTests(MultiCurrencyTestCase):
    """Test handling of deprecated multi-currency fields"""

    def test_deprecated_fields_exist_but_documented(self):
        """Test that deprecated fields still exist for backward compatibility"""
        journal = Journal.objects.create(
            organization=self.organization,
            journal_type=self.journal_type,
            period=self.period,
            journal_date=date.today(),
            currency_code='USD',
            status='draft',
            created_by=self.user
        )

        line = JournalLine.objects.create(
            journal=journal,
            line_number=1,
            account=self.cash_account,
            debit_amount=Decimal('1000.00'),
        )

        # Deprecated fields should exist
        self.assertTrue(hasattr(line, 'functional_debit_amount'))
        self.assertTrue(hasattr(line, 'functional_credit_amount'))

    def test_new_fields_preferred_over_deprecated(self):
        """Test that amount_txn and amount_base are the preferred fields"""
        journal = Journal.objects.create(
            organization=self.organization,
            journal_type=self.journal_type,
            period=self.period,
            journal_date=date.today(),
            currency_code='USD',
            exchange_rate=Decimal('133.333333'),
            status='draft',
            created_by=self.user
        )

        line = JournalLine.objects.create(
            journal=journal,
            line_number=1,
            account=self.cash_account,
            debit_amount=Decimal('1000.00'),
            txn_currency=self.usd,
            fx_rate=Decimal('133.333333'),
            amount_txn=Decimal('7.50'),
            amount_base=Decimal('1000.00')
        )

        # New fields should be populated
        self.assertEqual(line.amount_txn, Decimal('7.50'))
        self.assertEqual(line.amount_base, Decimal('1000.00'))
        self.assertEqual(line.fx_rate, Decimal('133.333333'))


class CurrencyServiceTests(MultiCurrencyTestCase):
    """Test the currency resolution service"""

    def test_resolvecurrency_same_currency(self):
        """Test that same currencies return 1.0"""
        rate = resolvecurrency(self.organization, 'USD', 'USD', date.today())
        self.assertEqual(rate, Decimal('1.000000'))

    def test_resolvecurrency_with_rate(self):
        """Test resolving exchange rate with existing rate"""
        rate = resolvecurrency(self.organization, 'USD', 'NPR', date.today())
        self.assertEqual(rate, Decimal('133.333333'))

    def test_resolvecurrency_no_rate(self):
        """Test fallback to 1.0 when no rate exists"""
        # Try a currency pair that doesn't exist
        rate = resolvecurrency(self.organization, 'EUR', 'NPR', date.today())
        self.assertEqual(rate, Decimal('1.000000'))

    def test_resolvecurrency_past_date(self):
        """Test finding rate for past date"""
        past_date = date.today() - timedelta(days=10)
        rate = resolvecurrency(self.organization, 'USD', 'NPR', past_date)
        self.assertEqual(rate, Decimal('133.333333'))  # Should find the rate
