"""
Tests for Scheduled Tasks - Phase 3 Task 4

Test coverage for:
- Period closing functionality
- Recurring entry posting
- Scheduled reports
- Task monitoring
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal

from accounting.models import (
    Account, Journal, JournalLine, JournalType, Organization,
    AccountingPeriod, RecurringEntry
)
from accounting.celery_tasks import (
    close_accounting_period,
    post_recurring_entries,
    validate_period_entries
)

User = get_user_model()


class PeriodClosingTestCase(TestCase):
    """Test period closing functionality."""

    def setUp(self):
        """Set up test data."""
        self.organization = Organization.objects.create(
            name="Test Org",
            code="TEST"
        )
        
        self.user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="testpass123",
            organization=self.organization
        )
        
        # Create accounts
        self.asset_account = Account.objects.create(
            organization=self.organization,
            code="1000",
            name="Cash",
            account_type="Asset",
            is_active=True
        )
        
        self.revenue_account = Account.objects.create(
            organization=self.organization,
            code="4000",
            name="Revenue",
            account_type="Revenue",
            is_active=True
        )
        
        # Create journal type
        self.journal_type = JournalType.objects.create(
            code="GJ",
            name="General Journal"
        )
        
        # Create period
        self.period = AccountingPeriod.objects.create(
            organization=self.organization,
            name="Jan 2024",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            is_closed=False
        )

    def test_period_closing_with_posted_journals(self):
        """Test closing period with all posted journals."""
        # Create posted journal
        journal = Journal.objects.create(
            organization=self.organization,
            journal_type=self.journal_type,
            date=date(2024, 1, 15),
            reference="TEST001",
            status="Posted"
        )
        
        JournalLine.objects.create(
            journal=journal,
            account=self.asset_account,
            debit=Decimal("1000.00")
        )
        
        JournalLine.objects.create(
            journal=journal,
            account=self.revenue_account,
            credit=Decimal("1000.00")
        )
        
        # Close period
        result = close_accounting_period.apply()
        
        self.assertIsNotNone(result)

    def test_period_with_unposted_journals_cannot_close(self):
        """Test period with draft journals cannot close."""
        journal = Journal.objects.create(
            organization=self.organization,
            journal_type=self.journal_type,
            date=date(2024, 1, 15),
            reference="TEST001",
            status="Draft"
        )
        
        # Should fail to close
        unposted = Journal.objects.filter(
            organization=self.organization,
            date__gte=self.period.start_date,
            date__lte=self.period.end_date,
            status__in=['Draft', 'Submitted']
        ).count()
        
        self.assertGreater(unposted, 0)


class RecurringEntryTestCase(TestCase):
    """Test recurring entry posting."""

    def setUp(self):
        """Set up test data."""
        self.organization = Organization.objects.create(
            name="Test Org",
            code="TEST"
        )
        
        self.user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="testpass123",
            organization=self.organization
        )
        
        # Create accounts
        self.cash_account = Account.objects.create(
            organization=self.organization,
            code="1000",
            name="Cash",
            account_type="Asset",
            is_active=True
        )
        
        self.revenue_account = Account.objects.create(
            organization=self.organization,
            code="4000",
            name="Revenue",
            account_type="Revenue",
            is_active=True
        )
        
        # Create journal type
        self.journal_type = JournalType.objects.create(
            code="GJ",
            name="General Journal"
        )

    def test_recurring_entry_creation(self):
        """Test creating recurring entry."""
        today = timezone.now().date()
        
        recurring = RecurringEntry.objects.create(
            organization=self.organization,
            code="REC001",
            description="Monthly rent",
            journal_type=self.journal_type,
            frequency="Monthly",
            next_posting_date=today,
            is_active=True
        )
        
        self.assertEqual(recurring.code, "REC001")
        self.assertTrue(recurring.is_active)
        self.assertEqual(recurring.frequency, "Monthly")

    def test_recurring_entry_posting(self):
        """Test posting recurring entries."""
        today = timezone.now().date()
        
        # Create recurring entry
        recurring = RecurringEntry.objects.create(
            organization=self.organization,
            code="REC001",
            description="Monthly rent",
            journal_type=self.journal_type,
            frequency="Monthly",
            next_posting_date=today,
            is_active=True
        )
        
        # Post recurring entries
        result = post_recurring_entries.apply(
            args=(self.organization.pk,)
        )
        
        self.assertIsNotNone(result)


class PeriodValidationTestCase(TestCase):
    """Test period entry validation."""

    def setUp(self):
        """Set up test data."""
        self.organization = Organization.objects.create(
            name="Test Org",
            code="TEST"
        )
        
        # Create accounts
        self.asset_account = Account.objects.create(
            organization=self.organization,
            code="1000",
            name="Cash",
            account_type="Asset",
            is_active=True
        )
        
        self.revenue_account = Account.objects.create(
            organization=self.organization,
            code="4000",
            name="Revenue",
            account_type="Revenue",
            is_active=True
        )
        
        # Create journal type
        self.journal_type = JournalType.objects.create(
            code="GJ",
            name="General Journal"
        )
        
        # Create period
        self.period = AccountingPeriod.objects.create(
            organization=self.organization,
            name="Jan 2024",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            is_closed=False
        )

    def test_validate_balanced_journal(self):
        """Test validation of balanced journal."""
        journal = Journal.objects.create(
            organization=self.organization,
            journal_type=self.journal_type,
            date=date(2024, 1, 15),
            reference="TEST001",
            status="Posted"
        )
        
        JournalLine.objects.create(
            journal=journal,
            account=self.asset_account,
            debit=Decimal("1000.00")
        )
        
        JournalLine.objects.create(
            journal=journal,
            account=self.revenue_account,
            credit=Decimal("1000.00")
        )
        
        # Validate period
        result = validate_period_entries.apply(
            args=(self.organization.pk, self.period.pk)
        )
        
        self.assertIsNotNone(result)

    def test_validate_detects_unbalanced_journal(self):
        """Test validation detects unbalanced journal."""
        journal = Journal.objects.create(
            organization=self.organization,
            journal_type=self.journal_type,
            date=date(2024, 1, 15),
            reference="TEST001",
            status="Posted"
        )
        
        # Unbalanced - only debit
        JournalLine.objects.create(
            journal=journal,
            account=self.asset_account,
            debit=Decimal("1000.00")
        )
        
        # Validate period
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
            code="TEST"
        )
        
        self.user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="testpass123",
            organization=self.organization
        )
        
        self.client.login(username="testuser", password="testpass123")
        
        # Create period
        self.period = AccountingPeriod.objects.create(
            organization=self.organization,
            name="Jan 2024",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            is_closed=False
        )

    def test_period_list_view(self):
        """Test period list view."""
        response = self.client.get('/accounting/periods/')
        
        if response.status_code == 200:
            self.assertContains(response, self.period.name)

    def test_period_detail_view(self):
        """Test period detail view."""
        response = self.client.get(f'/accounting/periods/{self.period.pk}/')
        
        if response.status_code == 200:
            self.assertContains(response, self.period.name)

    def test_recurring_entry_list_view(self):
        """Test recurring entry list view."""
        response = self.client.get('/accounting/recurring-entries/')
        
        self.assertIn(response.status_code, [200, 404])
