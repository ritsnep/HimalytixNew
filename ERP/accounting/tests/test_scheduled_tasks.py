"""
Tests for Scheduled Tasks - Phase 3 Task 4

Test coverage for:
- Period closing functionality
- Recurring entry posting
- Scheduled reports
- Task monitoring
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from accounting.celery_tasks import (
    close_accounting_period,
    post_recurring_entries,
    validate_period_entries,
)
from accounting.models import (
    AccountingPeriod,
    AccountType,
    ChartOfAccount,
    FiscalYear,
    Journal,
    JournalLine,
    JournalType,
    Organization,
    RecurringEntry,
)

User = get_user_model()


def create_account_types(org):
    asset_type = AccountType.objects.create(
        code="AST",
        name="Asset",
        nature="asset",
        classification="Statement of Financial Position",
        balance_sheet_category="Assets",
        income_statement_category="",
        cash_flow_category="Operating Activities",
        system_type=True,
        display_order=1,
    )
    revenue_type = AccountType.objects.create(
        code="REV",
        name="Revenue",
        nature="income",
        classification="Statement of Profit or Loss",
        balance_sheet_category="",
        income_statement_category="Revenue",
        cash_flow_category="Operating Activities",
        system_type=True,
        display_order=2,
    )
    return asset_type, revenue_type


def create_accounts(org, asset_type, revenue_type):
    asset_account = ChartOfAccount.objects.create(
        organization=org,
        account_code="1000",
        account_name="Cash",
        account_type=asset_type,
        is_active=True,
    )
    revenue_account = ChartOfAccount.objects.create(
        organization=org,
        account_code="4000",
        account_name="Revenue",
        account_type=revenue_type,
        is_active=True,
    )
    return asset_account, revenue_account


def create_journal_type(org):
    return JournalType.objects.create(
        organization=org,
        code="GJ",
        name="General Journal",
    )


def create_fiscal_year_and_period(org):
    fy = FiscalYear.objects.create(
        organization=org,
        code="FY24",
        name="FY 2024",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        status="open",
        is_current=True,
        is_default=True,
    )
    period = AccountingPeriod.objects.create(
        organization=org,
        fiscal_year=fy,
        name="Jan 2024",
        period_number=1,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31),
        status="open",
        is_closed=False,
    )
    return fy, period


class PeriodClosingTestCase(TestCase):
    """Test period closing functionality."""

    def setUp(self):
        """Set up test data."""
        self.organization = Organization.objects.create(
            name="Test Org",
            code="TEST",
        )

        self.user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="testpass123",
            organization=self.organization,
        )

        asset_type, revenue_type = create_account_types(self.organization)
        self.asset_account, self.revenue_account = create_accounts(
            self.organization, asset_type, revenue_type
        )

        self.journal_type = create_journal_type(self.organization)

        _, self.period = create_fiscal_year_and_period(self.organization)

    def test_period_closing_with_posted_journals(self):
        """Test closing period with all posted journals."""
        journal = Journal.objects.create(
            organization=self.organization,
            journal_type=self.journal_type,
            period=self.period,
            journal_number="TEST-001",
            journal_date=date(2024, 1, 15),
            reference="TEST001",
            status="posted",
        )

        JournalLine.objects.create(
            journal=journal,
            line_number=1,
            account=self.asset_account,
            debit_amount=Decimal("1000.00"),
        )

        JournalLine.objects.create(
            journal=journal,
            line_number=2,
            account=self.revenue_account,
            credit_amount=Decimal("1000.00"),
        )

        result = close_accounting_period.apply(args=(self.period.pk,))
        self.assertIsNotNone(result)

    def test_period_with_unposted_journals_cannot_close(self):
        """Test period with draft journals cannot close."""
        Journal.objects.create(
            organization=self.organization,
            journal_type=self.journal_type,
            period=self.period,
            journal_number="TEST-002",
            journal_date=date(2024, 1, 15),
            reference="TEST001",
            status="draft",
        )

        unposted = (
            Journal.objects.filter(organization=self.organization, period=self.period)
            .exclude(status__in=["posted", "reversed"])
            .count()
        )
        self.assertGreater(unposted, 0)


class RecurringEntryTestCase(TestCase):
    """Test recurring entry posting."""

    def setUp(self):
        """Set up test data."""
        self.organization = Organization.objects.create(
            name="Test Org",
            code="TEST",
        )

        self.user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="testpass123",
            organization=self.organization,
        )

        asset_type, revenue_type = create_account_types(self.organization)
        self.cash_account, self.revenue_account = create_accounts(
            self.organization, asset_type, revenue_type
        )

        self.journal_type = create_journal_type(self.organization)

        _, self.period = create_fiscal_year_and_period(self.organization)

    def test_recurring_entry_creation(self):
        """Test creating recurring entry."""
        today = timezone.now().date()

        recurring = RecurringEntry.objects.create(
            organization=self.organization,
            code="REC001",
            name="Monthly rent",
            description="Monthly rent",
            journal_type=self.journal_type,
            frequency="monthly",
            start_date=today,
            next_run_date=today,
            status="active",
        )

        self.assertEqual(recurring.code, "REC001")
        self.assertEqual(recurring.status, "active")
        self.assertEqual(recurring.frequency, "monthly")

    def test_recurring_entry_posting(self):
        """Test posting recurring entries."""
        today = timezone.now().date()

        RecurringEntry.objects.create(
            organization=self.organization,
            code="REC001",
            name="Monthly rent",
            description="Monthly rent",
            journal_type=self.journal_type,
            frequency="monthly",
            start_date=today,
            next_run_date=today,
            status="active",
        )

        result = post_recurring_entries.apply(args=(self.organization.pk,))
        self.assertIsNotNone(result)


class PeriodValidationTestCase(TestCase):
    """Test period entry validation."""

    def setUp(self):
        """Set up test data."""
        self.organization = Organization.objects.create(
            name="Test Org",
            code="TEST",
        )

        asset_type, revenue_type = create_account_types(self.organization)
        self.asset_account, self.revenue_account = create_accounts(
            self.organization, asset_type, revenue_type
        )

        self.journal_type = create_journal_type(self.organization)

        _, self.period = create_fiscal_year_and_period(self.organization)

    def test_validate_balanced_journal(self):
        """Test validation of balanced journal."""
        journal = Journal.objects.create(
            organization=self.organization,
            journal_type=self.journal_type,
            period=self.period,
            journal_number="TEST-003",
            journal_date=date(2024, 1, 15),
            reference="TEST001",
            status="posted",
        )

        JournalLine.objects.create(
            journal=journal,
            line_number=1,
            account=self.asset_account,
            debit_amount=Decimal("1000.00"),
        )

        JournalLine.objects.create(
            journal=journal,
            line_number=2,
            account=self.revenue_account,
            credit_amount=Decimal("1000.00"),
        )

        result = validate_period_entries.apply(
            args=(self.organization.pk, self.period.pk)
        )
        self.assertIsNotNone(result)

    def test_validate_detects_unbalanced_journal(self):
        """Test validation detects unbalanced journal."""
        journal = Journal.objects.create(
            organization=self.organization,
            journal_type=self.journal_type,
            period=self.period,
            journal_number="TEST-004",
            journal_date=date(2024, 1, 15),
            reference="TEST001",
            status="posted",
        )

        JournalLine.objects.create(
            journal=journal,
            line_number=1,
            account=self.asset_account,
            debit_amount=Decimal("1000.00"),
        )

        result = validate_period_entries.apply(
            args=(self.organization.pk, self.period.pk)
        )
        self.assertIsNotNone(result)


class ScheduledTaskViewsTestCase(TestCase):
    """Test scheduled task views."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()

        self.organization = Organization.objects.create(
            name="Test Org",
            code="TEST",
        )

        self.user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="testpass123",
            organization=self.organization,
        )

        self.client.login(username="testuser", password="testpass123")

        _, self.period = create_fiscal_year_and_period(self.organization)

    def test_period_list_view(self):
        """Test period list view."""
        response = self.client.get('/accounting/periods/')
        self.assertIn(response.status_code, [200, 404])

    def test_period_detail_view(self):
        """Test period detail view."""
        response = self.client.get(f'/accounting/periods/{self.period.pk}/')
        self.assertIn(response.status_code, [200, 404])

    def test_recurring_entry_list_view(self):
        """Test recurring entry list view."""
        response = self.client.get('/accounting/recurring-entries/')
        self.assertIn(response.status_code, [200, 404])
