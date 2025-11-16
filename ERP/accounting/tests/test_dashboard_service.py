from decimal import Decimal
from datetime import date

from django.test import TestCase

from accounting.models import (
    AccountType,
    Budget,
    BudgetLine,
    ChartOfAccount,
    Currency,
    FiscalYear,
    Organization,
    PurchaseInvoice,
    SalesInvoice,
    TaxCode,
)
from accounting.services.dashboard_service import DashboardService


class DashboardServiceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Dash Org', code='DASH', type='company')
        self.currency = Currency.objects.create(currency_code='USD', currency_name='US Dollar', symbol='$')
        account_type = AccountType.objects.create(
            code='EXP401',
            name='Expense',
            nature='expense',
            classification='Statement of Profit or Loss',
            balance_sheet_category=None,
            income_statement_category='Expense',
            cash_flow_category='Operating Activities',
            display_order=1,
        )
        self.account = ChartOfAccount.objects.create(
            organization=self.org,
            account_type=account_type,
            account_code='5005',
            account_name='Expense',
            currency=self.currency,
        )
        self.fiscal_year = FiscalYear.objects.create(
            organization=self.org,
            code='FY28',
            name='FY 2028',
            start_date=date(2028, 1, 1),
            end_date=date(2028, 12, 31),
            status='open',
            is_current=True,
        )
        self.budget = Budget.objects.create(
            organization=self.org,
            name='Budget',
            fiscal_year=self.fiscal_year,
            version='01',
            status='approved',
        )
        BudgetLine.objects.create(
            budget=self.budget,
            account=self.account,
            amount_by_month={str(i): Decimal('1000') for i in range(1, 13)},
        )
        self.tax_code = TaxCode.objects.create(
            organization=self.org,
            code='VAT',
            name='VAT',
            tax_type_id=1,
            tax_rate=Decimal('0.05'),
            rate=Decimal('0.05'),
        )
        PurchaseInvoice.objects.create(
            organization=self.org,
            vendor_id=1,
            vendor_display_name='Vendor',
            invoice_number='PI-1',
            invoice_date=date(2028, 1, 10),
            due_date=date(2028, 1, 30),
            currency=self.currency,
            exchange_rate=Decimal('1'),
            subtotal=Decimal('100'),
            tax_total=Decimal('5'),
            total=Decimal('105'),
            base_currency_total=Decimal('105'),
            status='posted',
        ).lines.create(
            line_number=1,
            account=self.account,
            description='Test',
            debit_amount=100,
            tax_code=self.tax_code,
            tax_amount=Decimal('5'),
        )
        SalesInvoice.objects.create(
            organization=self.org,
            customer_id=1,
            customer_display_name='Customer',
            invoice_number='SI-1',
            invoice_date=date(2028, 1, 10),
            due_date=date(2028, 2, 10),
            currency=self.currency,
            exchange_rate=Decimal('1'),
            subtotal=Decimal('200'),
            tax_total=Decimal('10'),
            total=Decimal('210'),
            base_currency_total=Decimal('210'),
            status='posted',
        ).lines.create(
            line_number=1,
            account=self.account,
            description='Sale',
            credit_amount=210,
            tax_code=self.tax_code,
            tax_amount=Decimal('10'),
        )

    def test_dashboard_metrics(self):
        service = DashboardService(self.org)
        metrics = service.get_dashboard_metrics()
        self.assertIn('ap_aging', metrics)
        self.assertIn('cash', metrics)
        self.assertIn('budget_variance', metrics)
        self.assertIn('tax_liabilities', metrics)
        self.assertIn('ap_aging_detail', metrics)
        detail = metrics['ap_aging_detail']
        self.assertTrue(detail['headers'])
        self.assertGreaterEqual(len(detail['rows']), 1)
        first = detail['rows'][0]
        self.assertEqual(first['vendor_name'], 'Vendor')
        self.assertEqual(len(first['buckets']), len(detail['headers']))
        self.assertEqual(first['total'], Decimal('105'))
