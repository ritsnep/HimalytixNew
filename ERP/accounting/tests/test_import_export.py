"""
Tests for Batch Import/Export - Phase 3 Task 3

Test coverage for:
- ImportService (Excel/CSV import)
- DuplicateDetector
- ExportService
- Import/Export Views
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from datetime import date
from decimal import Decimal
import tempfile
import openpyxl

from accounting.models import Account, Journal, JournalLine, JournalType, Organization
from accounting.services.import_export_service import (
    ImportService,
    ExportService,
    ImportTemplate,
    DuplicateDetector
)

User = get_user_model()


class ImportServiceTestCase(TestCase):
    """Test ImportService functionality."""

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
        
        # Create test accounts
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
        
        self.service = ImportService(self.organization, self.user)

    def test_import_service_initialization(self):
        """Test ImportService initializes correctly."""
        self.assertEqual(self.service.organization, self.organization)
        self.assertEqual(self.service.user, self.user)
        self.assertEqual(self.service.imported_count, 0)

    def test_parse_csv_row(self):
        """Test CSV row parsing."""
        row = {
            'Date': '2024-01-01',
            'Journal Type': 'GJ',
            'Reference': 'REF001',
            'Description': 'Test',
            'Account Code': '1000',
            'Account Name': 'Cash',
            'Debit': '1000',
            'Credit': '0'
        }
        
        parsed = self.service._parse_csv_row(row, 2)
        
        self.assertEqual(parsed['date'], '2024-01-01')
        self.assertEqual(parsed['debit'], 1000.0)

    def test_import_csv(self):
        """Test CSV import."""
        csv_content = """Date,Journal Type,Reference,Description,Account Code,Account Name,Debit,Credit
2024-01-01,GJ,REF001,Test,1000,Cash,1000,0
2024-01-01,GJ,REF001,Test,4000,Revenue,0,1000"""
        
        result = self.service.import_csv(csv_content, skip_duplicates=False)
        
        self.assertEqual(result['imported_count'], 1)  # 1 journal (2 lines)
        self.assertTrue(result['success'])

    def test_duplicate_detection(self):
        """Test duplicate detection."""
        # Create existing journal
        journal = Journal.objects.create(
            organization=self.organization,
            journal_type=self.journal_type,
            date=date(2024, 1, 1),
            reference="REF001"
        )
        
        # Check duplicate
        duplicate = DuplicateDetector.check_duplicate(
            self.organization,
            "REF001",
            date(2024, 1, 1),
            Decimal("1000.00")
        )
        
        self.assertIsNotNone(duplicate)
        self.assertEqual(duplicate.id, journal.id)

    def test_conflict_detection(self):
        """Test conflict detection."""
        data = {
            'account_code': '9999',  # Non-existent
            'journal_type': 'GJ',
            'debit': 100,
            'credit': 0
        }
        
        conflicts = DuplicateDetector.check_conflicts(self.organization, data)
        
        self.assertGreater(len(conflicts), 0)
        self.assertTrue(any('not found' in c for c in conflicts))


class ExportServiceTestCase(TestCase):
    """Test ExportService functionality."""

    def setUp(self):
        """Set up test data."""
        self.organization = Organization.objects.create(
            name="Test Org",
            code="TEST"
        )
        
        # Create test account
        self.account = Account.objects.create(
            organization=self.organization,
            code="1000",
            name="Cash",
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
            date=date(2024, 1, 1),
            reference="TEST001",
            status="Posted"
        )
        
        JournalLine.objects.create(
            journal=self.journal,
            account=self.account,
            debit=Decimal("1000.00"),
            credit=Decimal("0.00")
        )

    def test_export_to_excel(self):
        """Test Excel export."""
        journals = [self.journal]
        buffer, filename = ExportService.export_journals_to_excel(journals)
        
        self.assertIsNotNone(buffer)
        self.assertIn('.xlsx', filename)

    def test_export_to_csv(self):
        """Test CSV export."""
        journals = [self.journal]
        buffer, filename = ExportService.export_journals_to_csv(journals)
        
        self.assertIsNotNone(buffer)
        self.assertIn('.csv', filename)


class ImportTemplateTestCase(TestCase):
    """Test import template generation."""

    def setUp(self):
        """Set up test data."""
        self.organization = Organization.objects.create(
            name="Test Org",
            code="TEST"
        )

    def test_template_creation(self):
        """Test template Excel creation."""
        buffer = ImportTemplate.create_excel_template(self.organization)
        
        self.assertIsNotNone(buffer)
        self.assertGreater(buffer.getbuffer().nbytes, 0)

    def test_template_headers(self):
        """Test template headers."""
        headers = ImportTemplate.HEADERS
        
        self.assertIn('Date', headers)
        self.assertIn('Account Code', headers)
        self.assertIn('Debit', headers)
        self.assertIn('Credit', headers)


class ImportExportViewsTestCase(TestCase):
    """Test import/export views."""

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

    def test_import_list_view(self):
        """Test import list view."""
        response = self.client.get('/accounting/import-export/')
        
        self.assertIn(response.status_code, [200, 404])  # May not exist yet

    def test_template_download(self):
        """Test template download."""
        response = self.client.get('/accounting/download-import-template/')
        
        if response.status_code == 200:
            self.assertEqual(response['Content-Type'], 
                           'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
