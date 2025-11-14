from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from accounting.models import (
    AccountingPeriod,
    AccountType,
    ARReceipt,
    ChartOfAccount,
    Currency,
    Customer,
    CustomerContact,
    Dimension,
    DimensionValue,
    FiscalYear,
    Journal,
    JournalLine,
    JournalLineDimension,
    JournalType,
    PaymentTerm,
    PurchaseInvoice,
    SalesInvoice,
    Vendor,
    VendorContact,
)
from accounting.services.purchase_invoice_service import PurchaseInvoiceService
from accounting.services.sales_invoice_service import SalesInvoiceService, ReceiptAllocation
from accounting.services.app_payment_service import APPaymentService, PaymentAllocation
from usermanagement.models import CustomUser, Organization


class FinanceMasterDataTests(TestCase):
    def setUp(self):
        today = timezone.now().date()
        start_of_year = date(today.year, 1, 1)
        end_of_year = date(today.year, 12, 31)
        start_of_month = today.replace(day=1)
        next_month = (start_of_month + timedelta(days=32)).replace(day=1)
        end_of_month = next_month - timedelta(days=1)

        self.organization = Organization.objects.create(
            name='Test Org',
            code='TST',
            type='company',
        )
        self.currency = Currency.objects.create(
            currency_code='USD',
            currency_name='US Dollar',
            symbol='$',
        )
        self.liability_type = AccountType.objects.create(
            code='LIA100',
            name='Accounts Payable',
            nature='liability',
            classification='Statement of Financial Position',
            balance_sheet_category='Liabilities',
            income_statement_category=None,
            cash_flow_category='Operating Activities',
            display_order=1,
        )
        self.asset_type = AccountType.objects.create(
            code='AST100',
            name='Accounts Receivable',
            nature='asset',
            classification='Statement of Financial Position',
            balance_sheet_category='Assets',
            income_statement_category=None,
            cash_flow_category='Operating Activities',
            display_order=2,
        )
        self.income_type = AccountType.objects.create(
            code='INC100',
            name='Revenue',
            nature='income',
            classification='Statement of Profit or Loss',
            balance_sheet_category=None,
            income_statement_category='Revenue',
            cash_flow_category='Operating Activities',
            display_order=3,
        )
        self.expense_type = AccountType.objects.create(
            code='EXP100',
            name='Expense',
            nature='expense',
            classification='Statement of Profit or Loss',
            balance_sheet_category=None,
            income_statement_category='Expense',
            cash_flow_category='Operating Activities',
            display_order=4,
        )
        self.ap_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=self.liability_type,
            account_code='2000',
            account_name='Accounts Payable',
            currency=self.currency,
        )
        self.ar_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=self.asset_type,
            account_code='1100',
            account_name='Accounts Receivable',
            currency=self.currency,
        )
        self.revenue_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=self.income_type,
            account_code='4100',
            account_name='Revenue',
            currency=self.currency,
        )
        self.bank_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=self.asset_type,
            account_code='1010',
            account_name='Operating Bank',
            currency=self.currency,
        )
        self.expense_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=self.expense_type,
            account_code='5100',
            account_name='Supplies Expense',
            currency=self.currency,
        )
        self.ap_term = PaymentTerm.objects.create(
            organization=self.organization,
            code='PTAP',
            name='Net 30',
            term_type='ap',
            net_due_days=30,
        )
        self.ar_term = PaymentTerm.objects.create(
            organization=self.organization,
            code='PTAR',
            name='Net 15 2/5',
            term_type='ar',
            net_due_days=15,
            discount_percent=2,
            discount_days=5,
        )
        self.vendor = Vendor.objects.create(
            organization=self.organization,
            code='VENDMASTER',
            display_name='Main Vendor',
            payment_term=self.ap_term,
            accounts_payable_account=self.ap_account,
            default_currency=self.currency,
        )
        self.customer = Customer.objects.create(
            organization=self.organization,
            code='CUST-001',
            display_name='Acme Customer',
            payment_term=self.ar_term,
            accounts_receivable_account=self.ar_account,
            revenue_account=self.revenue_account,
            default_currency=self.currency,
        )
        self.fiscal_year = FiscalYear.objects.create(
            organization=self.organization,
            code=f'FY{today.year}',
            name=f'Fiscal {today.year}',
            start_date=start_of_year,
            end_date=end_of_year,
            status='open',
            is_current=True,
        )
        self.period = AccountingPeriod.objects.create(
            organization=self.organization,
            fiscal_year=self.fiscal_year,
            name='Current Month',
            period_number=1,
            start_date=start_of_month,
            end_date=end_of_month,
            status='open',
            is_current=True,
        )
        self.journal_type = JournalType.objects.create(
            organization=self.organization,
            code='PI',
            name='Purchase Invoice',
            auto_numbering_prefix='PI',
        )
        self.sales_journal_type = JournalType.objects.create(
            organization=self.organization,
            code='SI',
            name='Sales Invoice',
            auto_numbering_prefix='SI',
        )
        self.user = CustomUser.objects.create_user(
            username='ap_user',
            password='pass',
            organization=self.organization,
            full_name='AP User',
        )
        self.invoice_service = PurchaseInvoiceService(self.user)
        self.sales_invoice_service = SalesInvoiceService(self.user)
        self.ap_payment_service = APPaymentService(self.user)

    def test_payment_term_due_dates(self):
        invoice_date = date(2025, 1, 10)
        due_date = self.ap_term.calculate_due_date(invoice_date)
        discount_date = self.ar_term.calculate_discount_due_date(invoice_date)

        self.assertEqual(due_date, date(2025, 2, 9))
        self.assertEqual(discount_date, date(2025, 1, 15))

    def test_vendor_primary_contact_selection(self):
        vendor = Vendor.objects.create(
            organization=self.organization,
            code='VEND-001',
            display_name='Acme Supplies',
            legal_name='Acme Supplies LLC',
            payment_term=self.ap_term,
            accounts_payable_account=self.ap_account,
            default_currency=self.currency,
        )
        self.assertIsNone(vendor.primary_contact())

        first_contact = VendorContact.objects.create(
            vendor=vendor,
            name='Backup Contact',
            email='backup@example.com',
        )
        self.assertEqual(vendor.primary_contact(), first_contact)

        primary = VendorContact.objects.create(
            vendor=vendor,
            name='Primary Contact',
            email='primary@example.com',
            is_primary=True,
        )
        self.assertEqual(vendor.primary_contact(), primary)

    def test_dimension_assignment_links_to_journal_line(self):
        fiscal_year = FiscalYear.objects.create(
            organization=self.organization,
            code='FY25',
            name='FY2025',
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            status='open',
            is_current=True,
        )
        period = AccountingPeriod.objects.create(
            organization=self.organization,
            fiscal_year=fiscal_year,
            name='Jan 2025',
            period_number=1,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            status='open',
            is_current=True,
        )
        journal_type = JournalType.objects.create(
            organization=self.organization,
            code='GEN',
            name='General Journal',
            auto_numbering_prefix='GEN',
        )
        user = CustomUser.objects.create_user(
            username='poster',
            password='test-pass',
            organization=self.organization,
            full_name='Poster User',
        )
        journal = Journal.objects.create(
            organization=self.organization,
            journal_number='GEN-0001',
            journal_type=journal_type,
            period=period,
            journal_date=date(2025, 1, 15),
            currency_code='USD',
            created_by=user,
        )
        line = JournalLine.objects.create(
            journal=journal,
            line_number=1,
            account=self.ap_account,
            debit_amount=100,
            created_by=user,
        )
        dimension = Dimension.objects.create(
            organization=self.organization,
            code='DEPT',
            name='Department',
            dimension_type='department',
        )
        value = DimensionValue.objects.create(
            dimension=dimension,
            code='OPS',
            name='Operations',
        )

        JournalLineDimension.objects.create(
            journal_line=line,
            dimension=dimension,
            dimension_value=value,
        )

        self.assertEqual(line.dimensions.count(), 1)
        self.assertEqual(line.dimensions.first(), value)

    def test_purchase_invoice_service_creates_invoice_and_totals(self):
        invoice = self.invoice_service.create_invoice(
            organization=self.organization,
            vendor=self.vendor,
            invoice_number='PI-001',
            invoice_date=self.period.start_date,
            currency=self.currency,
            lines=[
                {
                    'description': 'Office Supplies',
                    'account': self.expense_account,
                    'quantity': Decimal('2'),
                    'unit_cost': Decimal('50'),
                }
            ],
        )
        self.assertIsInstance(invoice, PurchaseInvoice)
        self.assertEqual(invoice.total, Decimal('100'))
        self.assertEqual(invoice.status, 'draft')
        self.assertEqual(invoice.due_date, self.ap_term.calculate_due_date(self.period.start_date))

    def test_purchase_invoice_service_performs_three_way_match(self):
        invoice = self.invoice_service.create_invoice(
            organization=self.organization,
            vendor=self.vendor,
            invoice_number='PI-002',
            invoice_date=self.period.start_date,
            currency=self.currency,
            lines=[
                {
                    'description': 'Equipment',
                    'account': self.expense_account,
                    'quantity': Decimal('1'),
                    'unit_cost': Decimal('500'),
                    'po_reference': 'PO-1',
                    'receipt_reference': 'RCPT-1',
                }
            ],
        )
        self.invoice_service.perform_three_way_match(
            invoice,
            purchase_order_lines=[{'reference': 'PO-1', 'quantity': Decimal('1'), 'unit_cost': Decimal('500')}],
            receipt_lines=[{'reference': 'PO-1', 'quantity_received': Decimal('1')}],
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.match_status, 'matched')
        self.assertEqual(invoice.match_results.count(), 1)

    def test_purchase_invoice_service_posts_invoice(self):
        invoice = self.invoice_service.create_invoice(
            organization=self.organization,
            vendor=self.vendor,
            invoice_number='PI-003',
            invoice_date=self.period.start_date,
            currency=self.currency,
            lines=[
                {
                    'description': 'Consulting',
                    'account': self.expense_account,
                    'quantity': Decimal('1'),
                    'unit_cost': Decimal('750'),
                }
            ],
        )
        self.invoice_service.validate_invoice(invoice)
        posted_journal = self.invoice_service.post_invoice(invoice, self.journal_type)
        invoice.refresh_from_db()
        self.assertEqual(posted_journal.status, 'posted')
        self.assertEqual(invoice.status, 'posted')
        self.assertEqual(posted_journal.lines.count(), 2)  # one debit + one credit

    def test_sales_invoice_service_creates_invoice(self):
        invoice = self.sales_invoice_service.create_invoice(
            organization=self.organization,
            customer=self.customer,
            invoice_number='SI-001',
            invoice_date=self.period.start_date,
            currency=self.currency,
            lines=[
                {
                    'description': 'Consulting Revenue',
                    'revenue_account': self.revenue_account,
                    'quantity': Decimal('1'),
                    'unit_price': Decimal('1200'),
                }
            ],
        )
        self.assertIsInstance(invoice, SalesInvoice)
        self.assertEqual(invoice.total, Decimal('1200'))
        self.assertEqual(invoice.status, 'draft')

    def test_sales_invoice_service_posts_invoice(self):
        invoice = self.sales_invoice_service.create_invoice(
            organization=self.organization,
            customer=self.customer,
            invoice_number='SI-002',
            invoice_date=self.period.start_date,
            currency=self.currency,
            lines=[
                {
                    'description': 'Subscription',
                    'revenue_account': self.revenue_account,
                    'quantity': Decimal('2'),
                    'unit_price': Decimal('300'),
                }
            ],
        )
        self.sales_invoice_service.validate_invoice(invoice)
        posted = self.sales_invoice_service.post_invoice(invoice, self.sales_journal_type)
        invoice.refresh_from_db()
        self.assertEqual(posted.status, 'posted')
        self.assertEqual(invoice.status, 'posted')
        self.assertEqual(posted.lines.count(), 2)  # revenue + AR

    def test_sales_invoice_service_applies_receipt(self):
        invoice = self.sales_invoice_service.create_invoice(
            organization=self.organization,
            customer=self.customer,
            invoice_number='SI-003',
            invoice_date=self.period.start_date,
            currency=self.currency,
            lines=[
                {
                    'description': 'Hardware',
                    'revenue_account': self.revenue_account,
                    'quantity': Decimal('1'),
                    'unit_price': Decimal('500'),
                }
            ],
        )
        self.sales_invoice_service.validate_invoice(invoice)
        self.sales_invoice_service.post_invoice(invoice, self.sales_journal_type)
        receipt = self.sales_invoice_service.apply_receipt(
            organization=self.organization,
            customer=self.customer,
            receipt_number='RCPT-001',
            receipt_date=self.period.start_date,
            currency=self.currency,
            exchange_rate=Decimal('1'),
            amount=Decimal('500'),
            allocations={invoice: ReceiptAllocation(amount=Decimal('500'))},
        )
        self.assertIsInstance(receipt, ARReceipt)
        self.assertEqual(receipt.lines.count(), 1)

    def test_ap_payment_service_executes_payment(self):
        # Create and post purchase invoice
        invoice = self.invoice_service.create_invoice(
            organization=self.organization,
            vendor=self.vendor,
            invoice_number='PI-010',
            invoice_date=self.period.start_date,
            currency=self.currency,
            lines=[
                {
                    'description': 'Services',
                    'account': self.expense_account,
                    'quantity': Decimal('1'),
                    'unit_cost': Decimal('300'),
                }
            ],
        )
        self.invoice_service.validate_invoice(invoice)
        self.invoice_service.post_invoice(invoice, self.journal_type)

        payment = self.ap_payment_service.create_payment(
            organization=self.organization,
            vendor=self.vendor,
            payment_number='PAY-001',
            payment_date=self.period.start_date,
            bank_account=self.bank_account,
            currency=self.currency,
            exchange_rate=Decimal('1'),
            allocations=[PaymentAllocation(invoice=invoice, amount=Decimal('300'))],
        )
        self.ap_payment_service.approve_payment(payment, approver=self.user)
        executed = self.ap_payment_service.execute_payment(payment, self.journal_type)
        self.assertEqual(executed.status, 'executed')
        self.assertIsNotNone(executed.journal)
