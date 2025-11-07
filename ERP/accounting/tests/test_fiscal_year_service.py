from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.test import TestCase
from django.utils import timezone

from decimal import Decimal

from accounting.models import (
    AccountingPeriod,
    AccountingSettings,
    AccountType,
    ChartOfAccount,
    FiscalYear,
    Journal,
    JournalLine,
    JournalType,
)
from usermanagement.models import Organization
from accounting.services import post_journal
from accounting.services.fiscal_year_service import close_fiscal_year, reopen_fiscal_year


class FiscalYearServiceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.organization = Organization.objects.create(name="Org", code="ORG")
        self.user = User.objects.create_user(username="manager", password="pass123")
        self.user.organization = self.organization
        self.user.is_superuser = True
        self.user.save()

        self.asset_type = AccountType.objects.create(
            code="AST001",
            name="Assets",
            nature="asset",
            classification="IFRS Assets",
            display_order=1,
        )
        self.equity_type = AccountType.objects.create(
            code="EQT001",
            name="Equity",
            nature="equity",
            classification="IFRS Equity",
            display_order=2,
        )
        self.income_type = AccountType.objects.create(
            code="INC001",
            name="Revenue",
            nature="income",
            classification="IFRS Income",
            display_order=3,
        )
        self.expense_type = AccountType.objects.create(
            code="EXP001",
            name="Expense",
            nature="expense",
            classification="IFRS Expense",
            display_order=4,
        )
        self.cash_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=self.asset_type,
            account_code="1000",
            account_name="Cash",
        )
        self.retained_earnings = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=self.equity_type,
            account_code="3100",
            account_name="Retained Earnings",
        )
        self.current_year_income = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=self.equity_type,
            account_code="3200",
            account_name="Current Year Income",
        )
        self.revenue_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=self.income_type,
            account_code="4100",
            account_name="Revenue",
        )
        self.expense_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=self.expense_type,
            account_code="5100",
            account_name="Expense",
        )
        AccountingSettings.objects.create(
            organization=self.organization,
            retained_earnings_account=self.retained_earnings,
            current_year_income_account=self.current_year_income,
            auto_rollover_closing=True,
        )
        self.journal_type = JournalType.objects.create(
            organization=self.organization,
            code="GJ",
            name="General Journal",
            auto_numbering_prefix="GJ",
        )

        start = timezone.datetime(2024, 4, 1, tzinfo=timezone.utc)
        end = timezone.datetime(2025, 3, 31, tzinfo=timezone.utc)
        self.fiscal_year = FiscalYear.objects.create(
            organization=self.organization,
            code="FY24",
            name="FY 2024",
            start_date=start.date(),
            end_date=end.date(),
            is_current=True,
            created_by=self.user,
        )
        AccountingPeriod.objects.create(
            fiscal_year=self.fiscal_year,
            period_number=1,
            name="Apr 2024",
            start_date=start.date(),
            end_date=(start + timezone.timedelta(days=29)).date(),
            status="open",
            created_by=self.user,
        )
        AccountingPeriod.objects.create(
            fiscal_year=self.fiscal_year,
            period_number=2,
            name="May 2024",
            start_date=(start + timezone.timedelta(days=30)).date(),
            end_date=(start + timezone.timedelta(days=60)).date(),
            status="open",
            created_by=self.user,
        )
        self.next_year = FiscalYear.objects.create(
            organization=self.organization,
            code="FY25",
            name="FY 2025",
            start_date=end.date() + timezone.timedelta(days=1),
            end_date=end.date() + timezone.timedelta(days=365),
            is_current=False,
            created_by=self.user,
        )
        AccountingPeriod.objects.create(
            fiscal_year=self.next_year,
            period_number=1,
            name="Apr 2025",
            start_date=self.next_year.start_date,
            end_date=self.next_year.start_date + timezone.timedelta(days=29),
            status="open",
            created_by=self.user,
        )

    def test_close_fiscal_year_requires_closed_periods(self):
        with self.assertRaises(ValidationError):
            close_fiscal_year(self.fiscal_year, user=self.user, auto_close_open_periods=False)

        close_fiscal_year(self.fiscal_year, user=self.user, auto_close_open_periods=True)
        self.fiscal_year.refresh_from_db()
        self.assertEqual(self.fiscal_year.status, "closed")
        self.assertFalse(self.fiscal_year.is_current)
        self.assertEqual(self.fiscal_year.periods.filter(status="closed").count(), 2)

    def test_reopen_closed_fiscal_year(self):
        close_fiscal_year(self.fiscal_year, user=self.user, auto_close_open_periods=True)
        reopened = reopen_fiscal_year(self.fiscal_year, user=self.user)
        self.assertEqual(reopened.status, "open")
        self.assertTrue(reopened.is_current)

    def test_close_requires_permission(self):
        with self.assertRaises(PermissionDenied):
            close_fiscal_year(self.fiscal_year, user=None, auto_close_open_periods=True)

    def test_close_creates_closing_and_opening_entries(self):
        journal = Journal.objects.create(
            organization=self.organization,
            journal_type=self.journal_type,
            period=self.fiscal_year.periods.first(),
            journal_date=self.fiscal_year.start_date,
            status="draft",
        )
        JournalLine.objects.create(
            journal=journal,
            line_number=1,
            account=self.cash_account,
            debit_amount=Decimal("1000"),
        )
        JournalLine.objects.create(
            journal=journal,
            line_number=2,
            account=self.revenue_account,
            credit_amount=Decimal("1000"),
        )
        expense_journal = Journal.objects.create(
            organization=self.organization,
            journal_type=self.journal_type,
            period=self.fiscal_year.periods.first(),
            journal_date=self.fiscal_year.start_date + timezone.timedelta(days=1),
            status="draft",
        )
        JournalLine.objects.create(
            journal=expense_journal,
            line_number=1,
            account=self.expense_account,
            debit_amount=Decimal("600"),
        )
        JournalLine.objects.create(
            journal=expense_journal,
            line_number=2,
            account=self.cash_account,
            credit_amount=Decimal("600"),
        )
        post_journal(journal, user=self.user)
        post_journal(expense_journal, user=self.user)

        close_fiscal_year(self.fiscal_year, user=self.user, auto_close_open_periods=True)

        closing_journal = Journal.objects.filter(
            organization=self.organization,
            metadata__closing_type="year_end",
        ).first()
        self.assertIsNotNone(closing_journal)
        self.assertEqual(closing_journal.status, "posted")
        self.assertTrue(
            all(entry.is_closing_entry for entry in closing_journal.generalledger_set.all())
        )

        opening_journal = Journal.objects.filter(
            organization=self.organization,
            metadata__closing_type="year_opening",
        ).first()
        self.assertIsNotNone(opening_journal)
        self.assertEqual(opening_journal.status, "posted")

        self.retained_earnings.refresh_from_db()
        self.assertEqual(self.retained_earnings.current_balance, Decimal("-400"))
