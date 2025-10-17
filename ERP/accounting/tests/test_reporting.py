"""
Tests for Advanced Reporting System - Phase 3 Task 2

Comprehensive test coverage for:
- ReportService (6 report generators)
- ReportExportService (CSV/Excel/PDF export)
- Report Views (7 views)
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from datetime import datetime, date, timedelta
from decimal import Decimal
import json
import csv
from io import StringIO, BytesIO

from accounting.models import Account, Journal, JournalLine, JournalType
from accounting.services.report_service import ReportService
from accounting.services.report_export_service import ReportExportService
from usermanagement.models import Organization, User

User = get_user_model()


class ReportServiceTestCase(TestCase):
    """Test ReportService with 6 report types."""

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
            name="Sales Revenue",
            account_type="Revenue",
            is_active=True
        )
        
        self.expense_account = Account.objects.create(
            organization=self.organization,
            code="5000",
            name="Operating Expenses",
            account_type="Expense",
            is_active=True
        )
        
        self.ar_account = Account.objects.create(
            organization=self.organization,
            code="1100",
            name="Accounts Receivable",
            account_type="Asset",
            is_active=True
        )
        
        # Create journal type
        self.journal_type = JournalType.objects.create(
            code="GJ",
            name="General Journal"
        )
        
        # Create test journal
        self.journal = Journal.objects.create(
            organization=self.organization,
            journal_type=self.journal_type,
            date=date.today(),
            status="Posted"
        )
        
        # Create journal lines
        JournalLine.objects.create(
            journal=self.journal,
            account=self.cash_account,
            debit=Decimal("1000.00"),
            credit=Decimal("0.00"),
            description="Test debit"
        )
        
        JournalLine.objects.create(
            journal=self.journal,
            account=self.revenue_account,
            debit=Decimal("0.00"),
            credit=Decimal("1000.00"),
            description="Test credit"
        )
        
        self.service = ReportService(self.organization)

    def test_service_initialization(self):
        """Test ReportService initializes correctly."""
        self.assertEqual(self.service.organization, self.organization)

    def test_set_date_range(self):
        """Test setting date range."""
        start_date = date(2024, 1, 1)
        end_date = date(2024, 12, 31)
        
        self.service.set_date_range(start_date, end_date)
        
        self.assertEqual(self.service.start_date, start_date)
        self.assertEqual(self.service.end_date, end_date)

    def test_generate_trial_balance(self):
        """Test trial balance report generation."""
        self.service.set_date_range(
            date(2024, 1, 1),
            date(2024, 12, 31)
        )
        
        report = self.service.generate_trial_balance()
        
        self.assertIn('report_type', report)
        self.assertEqual(report['report_type'], 'trial_balance')
        self.assertIn('lines', report)
        self.assertIn('totals', report)
        self.assertTrue(isinstance(report['lines'], list))

    def test_generate_profit_loss(self):
        """Test P&L report generation."""
        self.service.set_date_range(
            date(2024, 1, 1),
            date(2024, 12, 31)
        )
        
        report = self.service.generate_profit_loss()
        
        self.assertIn('report_type', report)
        self.assertEqual(report['report_type'], 'profit_loss')
        self.assertIn('totals', report)
        self.assertIn('total_revenue', report['totals'])
        self.assertIn('total_expenses', report['totals'])
        self.assertIn('net_income', report['totals'])

    def test_generate_balance_sheet(self):
        """Test balance sheet report generation."""
        self.service.set_date_range(
            date(2024, 1, 1),
            date(2024, 12, 31)
        )
        
        report = self.service.generate_balance_sheet()
        
        self.assertIn('report_type', report)
        self.assertEqual(report['report_type'], 'balance_sheet')
        self.assertIn('is_balanced', report)
        self.assertIn('totals', report)

    def test_generate_general_ledger(self):
        """Test general ledger report generation."""
        self.service.set_date_range(
            date(2024, 1, 1),
            date(2024, 12, 31)
        )
        
        report = self.service.generate_general_ledger(
            account_id=self.cash_account.id
        )
        
        self.assertIn('report_type', report)
        self.assertEqual(report['report_type'], 'general_ledger')
        self.assertIn('lines', report)
        self.assertTrue(len(report['lines']) > 0)

    def test_generate_cash_flow(self):
        """Test cash flow report generation."""
        self.service.set_date_range(
            date(2024, 1, 1),
            date(2024, 12, 31)
        )
        
        report = self.service.generate_cash_flow()
        
        self.assertIn('report_type', report)
        self.assertEqual(report['report_type'], 'cash_flow')
        self.assertIn('totals', report)

    def test_generate_accounts_receivable_aging(self):
        """Test A/R aging report generation."""
        self.service.set_date_range(
            date(2024, 1, 1),
            date(2024, 12, 31)
        )
        
        report = self.service.generate_accounts_receivable_aging()
        
        self.assertIn('report_type', report)
        self.assertEqual(report['report_type'], 'ar_aging')
        self.assertIn('lines', report)


class ReportExportServiceTestCase(TestCase):
    """Test ReportExportService with 3 export formats."""

    def setUp(self):
        """Set up test data."""
        self.organization = Organization.objects.create(
            name="Test Org",
            code="TEST"
        )
        
        self.service = ReportService(self.organization)
        self.service.set_date_range(
            date(2024, 1, 1),
            date(2024, 12, 31)
        )
        
        # Create simple test report
        self.test_report = {
            'report_type': 'trial_balance',
            'organization': 'Test Org',
            'as_of_date': date(2024, 12, 31),
            'start_date': date(2024, 1, 1),
            'end_date': date(2024, 12, 31),
            'generated_at': datetime.now(),
            'is_balanced': True,
            'lines': [
                {
                    'account_code': '1000',
                    'account_name': 'Cash',
                    'account_type': 'Asset',
                    'debit_balance': Decimal('1000.00'),
                    'credit_balance': Decimal('0.00')
                }
            ],
            'totals': {
                'total_debits': Decimal('1000.00'),
                'total_credits': Decimal('0.00')
            }
        }

    def test_to_csv_export(self):
        """Test CSV export."""
        buffer, filename = ReportExportService.to_csv(self.test_report)
        
        self.assertIsNotNone(buffer)
        self.assertIsNotNone(filename)
        self.assertTrue(filename.endswith('.csv'))
        
        content = buffer.getvalue().decode('utf-8')
        self.assertIn('trial_balance', content)

    def test_to_excel_export(self):
        """Test Excel export."""
        try:
            buffer, filename = ReportExportService.to_excel(self.test_report)
            
            self.assertIsNotNone(buffer)
            self.assertIsNotNone(filename)
            self.assertTrue(filename.endswith('.xlsx'))
        except ImportError:
            self.skipTest("openpyxl not installed")

    def test_to_pdf_export(self):
        """Test PDF export."""
        try:
            buffer, filename = ReportExportService.to_pdf(self.test_report)
            
            self.assertIsNotNone(buffer)
            self.assertIsNotNone(filename)
            self.assertTrue(filename.endswith('.pdf'))
        except ImportError:
            self.skipTest("WeasyPrint not installed")


class ReportViewsTestCase(TestCase):
    """Test report views."""

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

    def test_report_list_view(self):
        """Test report list view."""
        response = self.client.get(reverse('accounting:report_list'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounting/reports/report_list.html')
        self.assertIn('reports', response.context)

    def test_general_ledger_view_no_params(self):
        """Test general ledger view without parameters."""
        response = self.client.get(reverse('accounting:report_ledger'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounting/reports/general_ledger.html')

    def test_trial_balance_view_no_params(self):
        """Test trial balance view without parameters."""
        response = self.client.get(reverse('accounting:report_trial_balance'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounting/reports/trial_balance.html')

    def test_profit_loss_view_no_params(self):
        """Test P&L view without parameters."""
        response = self.client.get(reverse('accounting:report_pl'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounting/reports/profit_loss.html')

    def test_balance_sheet_view_no_params(self):
        """Test balance sheet view without parameters."""
        response = self.client.get(reverse('accounting:report_bs'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounting/reports/balance_sheet.html')

    def test_cash_flow_view_no_params(self):
        """Test cash flow view without parameters."""
        response = self.client.get(reverse('accounting:report_cf'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounting/reports/cash_flow.html')

    def test_ar_aging_view_no_params(self):
        """Test A/R aging view without parameters."""
        response = self.client.get(reverse('accounting:report_ar_aging'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounting/reports/ar_aging.html')

    def test_unauthorized_access(self):
        """Test unauthorized access to reports."""
        self.client.logout()
        response = self.client.get(reverse('accounting:report_list'))
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)


class ReportExportViewTestCase(TestCase):
    """Test report export functionality."""

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

    def test_export_csv(self):
        """Test CSV export via view."""
        response = self.client.post(reverse('accounting:report_export'), {
            'report_type': 'trial_balance',
            'export_format': 'csv',
            'start_date': '2024-01-01',
            'end_date': '2024-12-31'
        })
        
        # Should return file download
        self.assertIn(response.status_code, [200, 404])  # 404 if no data

    def test_invalid_report_type(self):
        """Test invalid report type."""
        response = self.client.post(reverse('accounting:report_export'), {
            'report_type': 'invalid_report',
            'export_format': 'csv'
        })
        
        self.assertEqual(response.status_code, 400)

    def test_invalid_export_format(self):
        """Test invalid export format."""
        response = self.client.post(reverse('accounting:report_export'), {
            'report_type': 'trial_balance',
            'export_format': 'invalid'
        })
        
        self.assertEqual(response.status_code, 400)
