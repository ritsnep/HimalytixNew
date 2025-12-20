"""
Comprehensive tests for Daybook Report functionality.

Tests cover:
- Report generation with various filters
- Data accuracy and calculations
- Export functionality (CSV, Excel, PDF)
- URL routing and view access
- Permission handling
- Edge cases and error handling
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounting.models import (
    Journal, JournalLine, JournalType, ChartOfAccount, 
    AccountType, FiscalYear, AccountingPeriod
)
from usermanagement.models import Organization

User = get_user_model()


@pytest.mark.django_db
class TestDaybookReportView(TestCase):
    """Test suite for Daybook report view and functionality."""

    def setUp(self):
        """Set up test data for daybook report tests."""
        # Create organization
        self.organization = Organization.objects.create(
            name="Test Org",
            code="TEST001"
        )

        # Create user
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.user.organization = self.organization
        self.user.save()

        # Create fiscal year
        self.fiscal_year = FiscalYear.objects.create(
            organization=self.organization,
            fiscal_year_id="FY2024",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            is_active=True
        )

        # Create accounting period
        self.period = AccountingPeriod.objects.create(
            organization=self.organization,
            fiscal_year=self.fiscal_year,
            period_number=1,
            period_name="January 2024",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            status="open"
        )

        # Create account types
        self.asset_type = AccountType.objects.create(
            organization=self.organization,
            name="Asset",
            code="ASSET",
            normal_balance="debit"
        )

        self.liability_type = AccountType.objects.create(
            organization=self.organization,
            name="Liability",
            code="LIABILITY",
            normal_balance="credit"
        )

        # Create chart of accounts
        self.cash_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_code="1001",
            account_name="Cash",
            account_type=self.asset_type,
            is_active=True
        )

        self.payable_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_code="2001",
            account_name="Accounts Payable",
            account_type=self.liability_type,
            is_active=True
        )

        # Create journal types
        self.journal_type_general = JournalType.objects.create(
            organization=self.organization,
            code="GJ",
            name="General Journal",
            is_active=True
        )

        self.journal_type_payment = JournalType.objects.create(
            organization=self.organization,
            code="PY",
            name="Payment",
            is_active=True
        )

        # Create test journals with lines
        self._create_test_journals()

        self.client = Client()
        self.client.force_login(self.user)

    def _create_test_journals(self):
        """Create sample journal entries for testing."""
        # Journal 1 - Posted
        journal1 = Journal.objects.create(
            organization=self.organization,
            journal_number="JV-2024-001",
            journal_date=date(2024, 1, 15),
            journal_type=self.journal_type_general,
            period=self.period,
            description="Test Entry 1",
            status="posted",
            created_by=self.user,
            total_debit=Decimal("1000.00"),
            total_credit=Decimal("1000.00")
        )

        JournalLine.objects.create(
            journal=journal1,
            line_number=1,
            account=self.cash_account,
            description="Cash received",
            debit_amount=Decimal("1000.00"),
            credit_amount=Decimal("0.00")
        )

        JournalLine.objects.create(
            journal=journal1,
            line_number=2,
            account=self.payable_account,
            description="Liability cleared",
            debit_amount=Decimal("0.00"),
            credit_amount=Decimal("1000.00")
        )

        # Journal 2 - Draft
        journal2 = Journal.objects.create(
            organization=self.organization,
            journal_number="JV-2024-002",
            journal_date=date(2024, 1, 20),
            journal_type=self.journal_type_payment,
            period=self.period,
            description="Test Entry 2",
            status="draft",
            created_by=self.user,
            total_debit=Decimal("500.00"),
            total_credit=Decimal("500.00")
        )

        JournalLine.objects.create(
            journal=journal2,
            line_number=1,
            account=self.payable_account,
            description="Payment made",
            debit_amount=Decimal("500.00"),
            credit_amount=Decimal("0.00")
        )

        JournalLine.objects.create(
            journal=journal2,
            line_number=2,
            account=self.cash_account,
            description="Cash paid",
            debit_amount=Decimal("0.00"),
            credit_amount=Decimal("500.00")
        )

        # Journal 3 - Posted (different date)
        journal3 = Journal.objects.create(
            organization=self.organization,
            journal_number="JV-2024-003",
            journal_date=date(2024, 1, 25),
            journal_type=self.journal_type_general,
            period=self.period,
            description="Test Entry 3",
            status="posted",
            created_by=self.user,
            total_debit=Decimal("750.00"),
            total_credit=Decimal("750.00")
        )

        JournalLine.objects.create(
            journal=journal3,
            line_number=1,
            account=self.cash_account,
            description="Additional receipt",
            debit_amount=Decimal("750.00"),
            credit_amount=Decimal("0.00")
        )

        JournalLine.objects.create(
            journal=journal3,
            line_number=2,
            account=self.payable_account,
            description="Additional liability",
            debit_amount=Decimal("0.00"),
            credit_amount=Decimal("750.00")
        )

    def test_daybook_view_accessible(self):
        """Test that daybook view is accessible at the correct URL."""
        url = reverse('accounting:report_daybook')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounting/reports/daybook.html')

    def test_daybook_view_requires_authentication(self):
        """Test that daybook view requires user authentication."""
        self.client.logout()
        url = reverse('accounting:report_daybook')
        response = self.client.get(url)
        self.assertIn(response.status_code, [302, 403])  # Redirect or forbidden

    def test_daybook_report_generation_with_date_range(self):
        """Test daybook report generation with specific date range."""
        url = reverse('accounting:report_daybook')
        response = self.client.get(url, {
            'start_date': '2024-01-01',
            'end_date': '2024-01-31'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('report_data', response.context)
        
        report_data = response.context['report_data']
        self.assertIsNotNone(report_data)
        self.assertIn('rows', report_data)
        self.assertIn('totals', report_data)
        
        # Check that we have entries (3 journals × 2 lines each = 6 rows)
        self.assertGreater(len(report_data['rows']), 0)

    def test_daybook_totals_calculation(self):
        """Test that daybook totals are calculated correctly."""
        url = reverse('accounting:report_daybook')
        response = self.client.get(url, {
            'start_date': '2024-01-01',
            'end_date': '2024-01-31'
        })
        
        report_data = response.context['report_data']
        totals = report_data['totals']
        
        # Total debits should equal total credits
        self.assertEqual(totals['debit'], totals['credit'])
        
        # Expected totals: (1000 + 500 + 750) = 2250 for both debit and credit
        self.assertEqual(totals['debit'], Decimal('2250.00'))
        self.assertEqual(totals['credit'], Decimal('2250.00'))
        self.assertEqual(totals['balance'], Decimal('0.00'))

    def test_daybook_status_filter(self):
        """Test filtering daybook by transaction status."""
        url = reverse('accounting:report_daybook')
        
        # Filter for posted transactions only
        response = self.client.get(url, {
            'start_date': '2024-01-01',
            'end_date': '2024-01-31',
            'status': 'posted'
        })
        
        report_data = response.context['report_data']
        rows = report_data['rows']
        
        # All returned rows should have status 'posted'
        for row in rows:
            self.assertEqual(row['status'], 'posted')
        
        # Should have 4 lines (2 journals × 2 lines each)
        self.assertEqual(len(rows), 4)

    def test_daybook_journal_type_filter(self):
        """Test filtering daybook by journal type."""
        url = reverse('accounting:report_daybook')
        
        # Filter for general journal type
        response = self.client.get(url, {
            'start_date': '2024-01-01',
            'end_date': '2024-01-31',
            'journal_type': 'GJ'
        })
        
        report_data = response.context['report_data']
        rows = report_data['rows']
        
        # All returned rows should be from general journal
        for row in rows:
            self.assertEqual(row['journal_type_code'], 'GJ')

    def test_daybook_account_filter(self):
        """Test filtering daybook by specific account."""
        url = reverse('accounting:report_daybook')
        
        # Filter for cash account only
        response = self.client.get(url, {
            'start_date': '2024-01-01',
            'end_date': '2024-01-31',
            'account_id': str(self.cash_account.id)
        })
        
        report_data = response.context['report_data']
        rows = report_data['rows']
        
        # All returned rows should be for cash account
        for row in rows:
            self.assertEqual(row['account_code'], '1001')

    def test_daybook_voucher_number_search(self):
        """Test searching daybook by voucher number."""
        url = reverse('accounting:report_daybook')
        
        response = self.client.get(url, {
            'start_date': '2024-01-01',
            'end_date': '2024-01-31',
            'voucher_number': 'JV-2024-001'
        })
        
        report_data = response.context['report_data']
        rows = report_data['rows']
        
        # Should only return lines from JV-2024-001
        for row in rows:
            self.assertEqual(row['journal_number'], 'JV-2024-001')

    def test_daybook_export_csv(self):
        """Test exporting daybook report to CSV."""
        url = reverse('accounting:report_daybook')
        
        response = self.client.get(url, {
            'start_date': '2024-01-01',
            'end_date': '2024-01-31',
            'export': 'csv'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])

    def test_daybook_export_excel(self):
        """Test exporting daybook report to Excel."""
        url = reverse('accounting:report_daybook')
        
        response = self.client.get(url, {
            'start_date': '2024-01-01',
            'end_date': '2024-01-31',
            'export': 'excel'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('spreadsheet', response['Content-Type'])
        self.assertIn('attachment', response['Content-Disposition'])

    def test_daybook_export_pdf(self):
        """Test exporting daybook report to PDF."""
        url = reverse('accounting:report_daybook')
        
        response = self.client.get(url, {
            'start_date': '2024-01-01',
            'end_date': '2024-01-31',
            'export': 'pdf'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment', response['Content-Disposition'])

    def test_daybook_empty_results(self):
        """Test daybook report with no matching transactions."""
        url = reverse('accounting:report_daybook')
        
        # Query for a date range with no transactions
        response = self.client.get(url, {
            'start_date': '2024-02-01',
            'end_date': '2024-02-28'
        })
        
        report_data = response.context['report_data']
        self.assertEqual(len(report_data['rows']), 0)
        self.assertEqual(report_data['totals']['debit'], Decimal('0.00'))
        self.assertEqual(report_data['totals']['credit'], Decimal('0.00'))

    def test_daybook_transaction_count(self):
        """Test that transaction count is accurate."""
        url = reverse('accounting:report_daybook')
        
        response = self.client.get(url, {
            'start_date': '2024-01-01',
            'end_date': '2024-01-31'
        })
        
        report_data = response.context['report_data']
        
        # Should have 3 transactions (journals)
        self.assertEqual(report_data['totals']['transaction_count'], 3)

    def test_daybook_voucher_linking(self):
        """Test that voucher links are correctly formed."""
        url = reverse('accounting:report_daybook')
        
        response = self.client.get(url, {
            'start_date': '2024-01-01',
            'end_date': '2024-01-31'
        })
        
        report_data = response.context['report_data']
        rows = report_data['rows']
        
        # Each row should have a journal_id for linking
        for row in rows:
            self.assertIsNotNone(row['journal_id'])
            self.assertIsInstance(row['journal_id'], int)

    def test_daybook_combined_filters(self):
        """Test daybook with multiple filters combined."""
        url = reverse('accounting:report_daybook')
        
        response = self.client.get(url, {
            'start_date': '2024-01-01',
            'end_date': '2024-01-31',
            'status': 'posted',
            'journal_type': 'GJ',
            'account_id': str(self.cash_account.id)
        })
        
        report_data = response.context['report_data']
        rows = report_data['rows']
        
        # Verify all filters are applied
        for row in rows:
            self.assertEqual(row['status'], 'posted')
            self.assertEqual(row['journal_type_code'], 'GJ')
            self.assertEqual(row['account_code'], '1001')

    def test_daybook_context_data(self):
        """Test that all required context data is present."""
        url = reverse('accounting:report_daybook')
        
        response = self.client.get(url, {
            'start_date': '2024-01-01',
            'end_date': '2024-01-31'
        })
        
        context = response.context
        
        # Check for required context variables
        self.assertIn('start_date', context)
        self.assertIn('end_date', context)
        self.assertIn('journal_types', context)
        self.assertIn('accounts', context)
        self.assertIn('status_choices', context)
        self.assertIn('report_data', context)

    def test_daybook_date_ordering(self):
        """Test that daybook entries are ordered chronologically."""
        url = reverse('accounting:report_daybook')
        
        response = self.client.get(url, {
            'start_date': '2024-01-01',
            'end_date': '2024-01-31'
        })
        
        report_data = response.context['report_data']
        rows = report_data['rows']
        
        # Verify chronological ordering
        previous_date = None
        for row in rows:
            if previous_date:
                self.assertGreaterEqual(row['journal_date'], previous_date)
            previous_date = row['journal_date']


@pytest.mark.django_db
class TestDaybookReportService(TestCase):
    """Test suite for daybook report service layer."""

    def setUp(self):
        """Set up test data for service layer tests."""
        self.organization = Organization.objects.create(
            name="Test Org Service",
            code="TESTSVC001"
        )

    def test_daybook_service_initialization(self):
        """Test that report data service initializes correctly."""
        from reporting.services import ReportDataService
        
        service = ReportDataService(self.organization)
        self.assertEqual(service.organization, self.organization)

    def test_daybook_context_structure(self):
        """Test that daybook context has correct structure."""
        from reporting.services import ReportDataService
        from reporting.models import ReportDefinition
        
        service = ReportDataService(self.organization)
        
        definition = ReportDefinition(
            code="daybook",
            name="Daybook Report"
        )
        
        params = {
            'start_date': date(2024, 1, 1),
            'end_date': date(2024, 1, 31)
        }
        
        context = service.build_context(definition, params)
        
        # Verify structure
        self.assertIn('rows', context)
        self.assertIn('columns', context)
        self.assertIn('totals', context)
        self.assertIn('filters', context)
        self.assertIsInstance(context['rows'], list)
        self.assertIsInstance(context['totals'], dict)


# Run tests
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
