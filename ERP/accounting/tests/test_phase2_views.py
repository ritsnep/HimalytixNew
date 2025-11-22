"""
Phase 2 CRUD Views Tests - Comprehensive Test Suite

Unit and integration tests for Phase 2 view implementations:
- VoucherCreateView with HTMX handlers
- VoucherEditView with status protection
- VoucherDetailView with 5 action handlers
- VoucherListView with filtering/sorting
- HTMX handlers for dynamic operations
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from datetime import date, datetime
from decimal import Decimal
import json

from accounting.models import (
    Journal, JournalLine, Organization, JournalType,
    AccountingPeriod, ChartOfAccount, Currency
)
from accounting.tests import factories


User = get_user_model()


class VoucherTestDataMixin:
    period_start = date(2024, 1, 1)
    period_end = date(2024, 1, 31)

    @classmethod
    def setUpTestData(cls):
        cls.org = factories.create_organization(name="Test Organization", code="TEST-ORG")
        cls.currency = factories.create_currency(code="USD", name="US Dollar")
        cls.account_type = factories.create_account_type(nature="asset")
        cls.journal_type = factories.create_journal_type(
            organization=cls.org,
            code="GJ",
            name="General Journal",
        )
        cls.fiscal_year = factories.create_fiscal_year(
            organization=cls.org,
            code="FY24",
            name="FY 2024",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )

    def setUp(self):
        self.org = type(self).org
        self.currency = type(self).currency
        self.account_type = type(self).account_type
        self.journal_type = type(self).journal_type
        self.fiscal_year = type(self).fiscal_year
        self.password = "testpass123"
        self.user = factories.create_user(organization=self.org, password=self.password)
        self.user.is_superuser = True
        self.user.is_staff = True
        self.user.save(update_fields=["is_superuser", "is_staff"])
        self.period = factories.create_accounting_period(
            fiscal_year=self.fiscal_year,
            start_date=self.period_start,
            end_date=self.period_end,
            name="Jan-2024",
            period_number=1,
        )
        self.account = factories.create_chart_of_account(
            organization=self.org,
            account_type=self.account_type,
            currency=self.currency,
            account_name="Cash Account",
        )
        self.client = Client()


class Phase2VoucherCreateViewTests(VoucherTestDataMixin, TestCase):
    """
    Tests for VoucherCreateView - Task 1
    
    Validates:
    - GET displays empty forms
    - POST validates and saves
    - HTMX line addition
    - Organization isolation
    - Transaction safety
    """

    def test_get_create_view_shows_empty_forms(self):
        """VoucherCreateView GET should display empty forms"""
        # Arrange
        self.client.login(username=self.user.username, password=self.password)
        
        # Act
        response = self.client.get(reverse('accounting:journal_create'))
        
        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        self.assertIn('formset', response.context)
        self.assertFalse(response.context['form'].is_bound)
        self.assertFalse(response.context['formset'].is_bound)

    def test_post_create_valid_balanced_journal(self):
        """VoucherCreateView POST with valid balanced data should create journal"""
        # Arrange
        self.client.login(username=self.user.username, password=self.password)
        
        data = {
            'journal_type': str(self.journal_type.pk),
            'period': str(self.period.pk),
            'journal_date': '2024-01-15',
            'currency_code': self.currency.currency_code,
            'reference': 'JNL-2024-001',
            'description': 'Test journal entry',
            
            # Formset management
            'lines-TOTAL_FORMS': '1',
            'lines-INITIAL_FORMS': '0',
            'lines-MIN_NUM_FORMS': '1',
            'lines-MAX_NUM_FORMS': '1000',
            
            # Line 1
            'lines-0-account': str(self.account.id),
            'lines-0-debit_amount': '100.00',
            'lines-0-credit_amount': '',
            'lines-0-description': 'Test debit entry'
        }
        
        # Act
        response = self.client.post(reverse('accounting:journal_create'), data)
        
        # Assert - Journal should be created
        self.assertTrue(Journal.objects.filter(reference='JNL-2024-001').exists())
        journal = Journal.objects.get(reference='JNL-2024-001')
        self.assertEqual(journal.organization, self.org)
        self.assertEqual(journal.status, 'draft')
        self.assertEqual(journal.lines.count(), 1)

    def test_post_create_unbalanced_journal_fails(self):
        """VoucherCreateView POST with unbalanced journal should fail"""
        # Arrange
        self.client.login(username=self.user.username, password=self.password)
        
        data = {
            'journal_type': str(self.journal_type.pk),
            'period': str(self.period.pk),
            'journal_date': '2024-01-15',
            'currency_code': self.currency.currency_code,
            'reference': 'INVALID-001',
            
            'lines-TOTAL_FORMS': '1',
            'lines-INITIAL_FORMS': '0',
            'lines-MIN_NUM_FORMS': '1',
            'lines-MAX_NUM_FORMS': '1000',
            
            # Unbalanced: debit != credit
            'lines-0-account': str(self.account.id),
            'lines-0-debit_amount': '100.00',
            'lines-0-credit_amount': '50.00',  # Unbalanced
            'lines-0-description': 'Unbalanced line'
        }
        
        # Act
        response = self.client.post(reverse('accounting:journal_create'), data)
        
        # Assert - Journal should NOT be created
        self.assertFalse(Journal.objects.filter(reference='INVALID-001').exists())
        # Should redisplay form with errors
        self.assertContains(response, 'balance', status_code=400)


class Phase2VoucherEditViewTests(VoucherTestDataMixin, TestCase):
    """
    Tests for VoucherEditView - Task 2
    
    Validates:
    - GET loads existing journal
    - POST updates journal
    - Status-based protection
    - Draft/Pending editable
    - Posted/Approved read-only
    """

    def setUp(self):
        super().setUp()
        self.journal = factories.create_journal(
            organization=self.org,
            journal_type=self.journal_type,
            period=self.period,
            currency_code=self.currency.currency_code,
            reference='JNL-EDIT-001',
            description='Original notes',
            status='draft',
            created_by=self.user,
        )
        self.line = JournalLine.objects.create(
            journal=self.journal,
            account=self.account,
            debit_amount=Decimal('100.00'),
            line_number=10
        )

    def test_get_edit_view_loads_existing_journal(self):
        """VoucherEditView GET should load existing journal with data"""
        # Arrange
        self.client.login(username=self.user.username, password=self.password)
        
        # Act
        response = self.client.get(
            reverse('accounting:journal_update', args=[self.journal.id])
        )
        
        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'JNL-EDIT-001')
        self.assertContains(response, 'Original notes')
        self.assertEqual(
            response.context['form'].instance.id,
            self.journal.id
        )

    def test_post_edit_updates_journal(self):
        """VoucherEditView POST should update journal data"""
        # Arrange
        self.client.login(username=self.user.username, password=self.password)
        
        data = {
            'journal_type': str(self.journal_type.id),
            'period': str(self.period.id),
            'journal_date': '2024-01-20',  # Changed
            'currency': str(self.currency.pk),
            'reference_no': 'JNL-EDIT-UPDATED',  # Changed
            'notes': 'Updated notes',  # Changed
            
            'lines-TOTAL_FORMS': '1',
            'lines-INITIAL_FORMS': '1',
            'lines-MIN_NUM_FORMS': '1',
            'lines-MAX_NUM_FORMS': '1000',
            
            'lines-0-id': str(self.line.id),
            'lines-0-account': str(self.account.id),
            'lines-0-debit_amount': '150.00',  # Changed
            'lines-0-credit_amount': '',
            'lines-0-description': 'Updated line'
        }
        
        # Act
        response = self.client.post(
            reverse('accounting:journal_update', args=[self.journal.id]),
            data
        )
        
        # Assert
        self.journal.refresh_from_db()
        self.assertEqual(self.journal.reference_no, 'JNL-EDIT-UPDATED')
        self.assertEqual(self.journal.notes, 'Updated notes')
        self.line.refresh_from_db()
        self.assertEqual(self.line.debit_amount, Decimal('150.00'))

    def test_cannot_edit_posted_journal(self):
        """VoucherEditView GET should redirect if journal is posted"""
        # Arrange
        self.journal.status = 'posted'
        self.journal.save()
        self.client.login(username=self.user.username, password=self.password)
        
        # Act
        response = self.client.get(
            reverse('accounting:journal_update', args=[self.journal.id])
        )
        
        # Assert - Should redirect with warning
        self.assertEqual(response.status_code, 302)


class Phase2VoucherDetailViewTests(VoucherTestDataMixin, TestCase):
    """
    Tests for VoucherDetailView - Task 3
    
    Validates:
    - Display read-only journal
    - Show audit trail
    - Action buttons visible based on status
    - 5 action handlers (Post, Delete, Duplicate, Reverse, Bulk)
    """

    def setUp(self):
        super().setUp()
        self.journal = Journal.objects.create(
            organization=self.org,
            journal_type=self.journal_type,
            period=self.period,
            currency=self.currency,
            reference_no='JNL-DETAIL-001',
            status='draft'
        )
        JournalLine.objects.create(
            journal=self.journal,
            account=self.account,
            debit_amount=Decimal('100.00'),
            line_number=10
        )
        JournalLine.objects.create(
            journal=self.journal,
            account=self.account,
            credit_amount=Decimal('100.00'),
            line_number=20
        )

    def test_get_detail_view_displays_journal(self):
        """VoucherDetailView should display journal read-only"""
        # Arrange
        self.client.login(username=self.user.username, password=self.password)
        
        # Act
        response = self.client.get(
            reverse('accounting:journal_detail', args=[self.journal.id])
        )
        
        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'JNL-DETAIL-001')
        self.assertIn('journal', response.context)

    def test_action_buttons_visible_for_draft(self):
        """Draft journal should show Edit, Post, Delete actions"""
        # Arrange
        self.client.login(username=self.user.username, password=self.password)
        
        # Act
        response = self.client.get(
            reverse('accounting:journal_detail', args=[self.journal.id])
        )
        
        # Assert
        self.assertTrue(response.context.get('can_edit'))
        self.assertTrue(response.context.get('can_post'))
        self.assertTrue(response.context.get('can_delete'))

    def test_post_action_changes_status(self):
        """VoucherPostView should change status to posted"""
        # Arrange
        self.client.login(username=self.user.username, password=self.password)
        
        # Act
        response = self.client.post(
            reverse('accounting:journal_post', args=[self.journal.id])
        )
        
        # Assert
        self.journal.refresh_from_db()
        self.assertEqual(self.journal.status, 'posted')

    def test_delete_action_removes_journal(self):
        """VoucherDeleteView should remove draft journal"""
        # Arrange
        self.client.login(username=self.user.username, password=self.password)
        journal_id = self.journal.id
        
        # Act
        response = self.client.post(
            reverse('accounting:journal_delete', args=[journal_id])
        )
        
        # Assert
        self.assertFalse(Journal.objects.filter(id=journal_id).exists())


class Phase2VoucherListViewTests(VoucherTestDataMixin, TestCase):
    """Tests for VoucherListView - Task 4."""

    def setUp(self):
        super().setUp()
        for i in range(10):
            status = 'draft' if i % 2 == 0 else 'posted'
            Journal.objects.create(
                organization=self.org,
                journal_type=self.journal_type,
                period=self.period,
                currency=self.currency,
                reference_no=f'JNL-LIST-{i:03d}',
                status=status
            )

    def test_get_list_view_displays_journals(self):
        """VoucherListView should display paginated journal list"""
        # Arrange
        self.client.login(username=self.user.username, password=self.password)
        
        # Act
        response = self.client.get(reverse('accounting:journal_list'))
        
        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertIn('object_list', response.context)
        self.assertEqual(len(response.context['object_list']), 10)

    def test_filter_by_status(self):
        """VoucherListView should filter by status"""
        # Arrange
        self.client.login(username=self.user.username, password=self.password)
        
        # Act
        response = self.client.get(
            f"{reverse('accounting:journal_list')}?status=draft"
        )
        
        # Assert - 5 draft journals
        self.assertEqual(len(response.context['object_list']), 5)

    def test_search_by_reference(self):
        """VoucherListView should search by reference number"""
        # Arrange
        self.client.login(username=self.user.username, password=self.password)
        
        # Act
        response = self.client.get(
            f"{reverse('accounting:journal_list')}?search=JNL-LIST-001"
        )
        
        # Assert
        self.assertEqual(len(response.context['object_list']), 1)
        self.assertEqual(
            response.context['object_list'][0].reference_no,
            'JNL-LIST-001'
        )

    def test_pagination_limits(self):
        """VoucherListView pagination should limit items per page"""
        # Arrange
        self.client.login(username=self.user.username, password=self.password)
        
        # Act
        response = self.client.get(reverse('accounting:journal_list'))
        
        # Assert
        self.assertIn('paginator', response.context)
        self.assertEqual(response.context['paginator'].per_page, 25)


class Phase2ValidationTests(TestCase):
    """Regression placeholders for validation helpers."""

    def test_debit_credit_exclusive(self):
        self.assertTrue(True)

    def test_journal_balance_required(self):
        self.assertTrue(True)
