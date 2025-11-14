from datetime import date
from decimal import Decimal

from django.test import TestCase

from accounting.models import (
    AccountType,
    Asset,
    AssetCategory,
    ChartOfAccount,
    Currency,
    FiscalYear,
    JournalType,
    Organization,
)
from accounting.services.depreciation_service import DepreciationService
from usermanagement.models import CustomUser


class DepreciationServiceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='FA Org', code='FA', type='company')
        self.currency = Currency.objects.create(currency_code='USD', currency_name='US Dollar', symbol='$')
        self.fiscal_year = FiscalYear.objects.create(
            organization=self.org,
            code='FY27',
            name='FY 2027',
            start_date=date(2027, 1, 1),
            end_date=date(2027, 12, 31),
            status='open',
            is_current=True,
        )
        self.journal_type = JournalType.objects.create(
            organization=self.org,
            code='DEP',
            name='Depreciation',
        )
        acc_type = AccountType.objects.create(
            code='EXP201',
            name='Depreciation Expense',
            nature='expense',
            classification='Statement of Profit or Loss',
            balance_sheet_category=None,
            income_statement_category='Expense',
            cash_flow_category='Operating Activities',
            display_order=1,
        )
        self.expense_account = ChartOfAccount.objects.create(
            organization=self.org,
            account_type=acc_type,
            account_code='5600',
            account_name='Depreciation Expense',
            currency=self.currency,
        )
        acc_type2 = AccountType.objects.create(
            code='ACC201',
            name='Accumulated Depreciation',
            nature='contra',
            classification='Statement of Financial Position',
            balance_sheet_category='Assets',
            income_statement_category=None,
            cash_flow_category='Operating Activities',
            display_order=2,
        )
        self.accumulated_account = ChartOfAccount.objects.create(
            organization=self.org,
            account_type=acc_type2,
            account_code='1700',
            account_name='Accumulated Depreciation',
            currency=self.currency,
        )
        self.category = AssetCategory.objects.create(
            organization=self.org,
            name='Office Equipment',
            depreciation_expense_account=self.expense_account,
            accumulated_depreciation_account=self.accumulated_account,
        )
        self.asset = Asset.objects.create(
            organization=self.org,
            name='Laptop',
            category=self.category,
            acquisition_date=date(2027, 1, 10),
            cost=Decimal('1200'),
            salvage_value=Decimal('200'),
            useful_life_years=Decimal('3'),
        )
        self.user = CustomUser.objects.create_user(username='deprec', password='test', organization=self.org)
        self.service = DepreciationService(self.user, self.journal_type)

    def test_straight_line_depreciation_posts_journal(self):
        journal = self.service.post_period(date(2027, 1, 31), self.expense_account, self.accumulated_account)
        self.assertEqual(journal.status, 'posted')
        asset = Asset.objects.get(pk=self.asset.pk)
        self.assertGreater(asset.accumulated_depreciation, Decimal('0'))
