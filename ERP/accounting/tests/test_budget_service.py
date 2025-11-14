from decimal import Decimal

from django.test import TestCase

from accounting.models import (
    AccountType,
    Budget,
    BudgetLine,
    ChartOfAccount,
    Currency,
    FiscalYear,
    Organization,
)
from accounting.services.budget_service import BudgetService


class BudgetServiceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Budget House', code='BUD', type='company')
        self.currency = Currency.objects.create(currency_code='USD', currency_name='US Dollar', symbol='$')
        self.fiscal_year = FiscalYear.objects.create(
            organization=self.org,
            code='FY26',
            name='FY 2026',
            start_date='2026-01-01',
            end_date='2026-12-31',
            status='open',
            is_current=True,
        )
        acc_type = AccountType.objects.create(
            code='EXP101',
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
            account_type=acc_type,
            account_code='5000',
            account_name='Marketing Expense',
            currency=self.currency,
        )
        self.budget = Budget.objects.create(
            organization=self.org,
            name='Marketing FY26',
            fiscal_year=self.fiscal_year,
            version='01',
            status='approved',
        )

    def test_calculate_variancesuses_actuals(self):
        BudgetLine.objects.create(
            budget=self.budget,
            account=self.account,
            amount_by_month={str(i): Decimal('1000') for i in range(1, 13)},
        )
        service = BudgetService(self.budget)
        variances = service.calculate_variances()
        self.assertEqual(len(variances), 1)
        row = variances[0]
        self.assertEqual(row.account_id, self.account.pk)
        self.assertEqual(row.budget_amount, Decimal('12000'))
        self.assertEqual(row.actual_amount, Decimal('0'))
        self.assertEqual(row.variance, Decimal('12000'))
