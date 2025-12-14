from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from rest_framework.authtoken.models import Token
from django.contrib.auth import get_user_model
from accounting.models import (
    Organization, Journal, JournalType, AccountingPeriod, FiscalYear,
    Account, JournalLine, ApprovalWorkflow, ApprovalStep
)
import datetime
from decimal import Decimal
import json

from accounting.tests import factories as fac
from configuration.models import ConfigurationEntry
from configuration.services import ConfigurationService

User = get_user_model()

# ============================================================================
# API Authentication Tests
# ============================================================================

class APIAuthenticationTestCase(APITestCase):
    """Test REST API authentication and permissions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.organization1 = Organization.objects.create(name='Organization 1')
        self.organization2 = Organization.objects.create(name='Organization 2')
        
        self.user1 = User.objects.create_user(
            username='user1', 
            password='testpass123',
            organization=self.organization1
        )
        self.user2 = User.objects.create_user(
            username='user2',
            password='testpass123',
            organization=self.organization2
        )
        
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='adminpass123',
            organization=self.organization1
        )
    
    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated users cannot access API."""
        response = self.client.get('/api/v1/accounts/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_authenticated_access_granted(self):
        """Test that authenticated users can access API."""
        self.client.force_authenticate(user=self.user1)
        response = self.client.get('/api/v1/accounts/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_organization_isolation(self):
        """Test that users only see their organization's data."""
        # Create accounts for both organizations
        Account.objects.create(
            organization=self.organization1,
            code='1000',
            name='Cash - Org1',
            account_type='ASSET'
        )
        Account.objects.create(
            organization=self.organization2,
            code='1000',
            name='Cash - Org2',
            account_type='ASSET'
        )
        
        # User1 should only see Org1 accounts
        self.client.force_authenticate(user=self.user1)
        response = self.client.get('/api/v1/accounts/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'Cash - Org1')


# ============================================================================
# Account API Tests
# ============================================================================

class AccountAPITestCase(APITestCase):
    """Test Account REST API endpoints."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.organization = Organization.objects.create(name='Test Org')
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            organization=self.organization
        )
        self.client.force_authenticate(user=self.user)
        
        # Create test accounts
        self.asset_account = Account.objects.create(
            organization=self.organization,
            code='1000',
            name='Cash',
            account_type='ASSET'
        )
        self.liability_account = Account.objects.create(
            organization=self.organization,
            code='2000',
            name='Accounts Payable',
            account_type='LIABILITY'
        )
    
    def test_list_accounts(self):
        """Test listing all accounts."""
        response = self.client.get('/api/v1/accounts/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_create_account(self):
        """Test creating a new account."""
        data = {
            'code': '3000',
            'name': 'Revenue',
            'account_type': 'REVENUE'
        }
        response = self.client.post('/api/v1/accounts/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Account.objects.count(), 3)
    
    def test_retrieve_account(self):
        """Test retrieving a specific account."""
        response = self.client.get(f'/api/v1/accounts/{self.asset_account.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Cash')
    
    def test_update_account(self):
        """Test updating an account."""
        data = {'name': 'Cash and Cash Equivalents'}
        response = self.client.patch(
            f'/api/v1/accounts/{self.asset_account.id}/',
            data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.asset_account.refresh_from_db()
        self.assertEqual(self.asset_account.name, 'Cash and Cash Equivalents')
    
    def test_delete_account(self):
        """Test deleting an account."""
        response = self.client.delete(f'/api/v1/accounts/{self.asset_account.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Account.objects.count(), 1)
    
    def test_filter_accounts_by_type(self):
        """Test filtering accounts by type."""
        response = self.client.get('/api/v1/accounts/by_type/?type=ASSET')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['account_type'], 'ASSET')
    
    def test_get_account_balance(self):
        """Test getting account balance."""
        response = self.client.get(f'/api/v1/accounts/{self.asset_account.id}/balance/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('balance', response.data)


# ============================================================================
# Journal API Tests
# ============================================================================

class JournalAPITestCase(APITestCase):
    """Test Journal REST API endpoints."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.organization = Organization.objects.create(name='Test Org')
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            organization=self.organization
        )
        self.client.force_authenticate(user=self.user)
        
        # Create fiscal year and period
        self.fiscal_year = FiscalYear.objects.create(
            organization=self.organization,
            code='FY2025',
            name='Fiscal Year 2025',
            start_date=datetime.date(2025, 1, 1),
            end_date=datetime.date(2025, 12, 31)
        )
        self.period = AccountingPeriod.objects.create(
            fiscal_year=self.fiscal_year,
            period_number=1,
            name='January',
            start_date=datetime.date(2025, 1, 1),
            end_date=datetime.date(2025, 1, 31)
        )
        
        # Create journal type
        self.journal_type = JournalType.objects.create(
            organization=self.organization,
            code='GJ',
            name='General Journal'
        )
        
        # Create accounts
        self.debit_account = Account.objects.create(
            organization=self.organization,
            code='1000',
            name='Cash',
            account_type='ASSET'
        )
        self.credit_account = Account.objects.create(
            organization=self.organization,
            code='3000',
            name='Revenue',
            account_type='REVENUE'
        )
    
    def test_list_journals(self):
        """Test listing all journals."""
        Journal.objects.create(
            organization=self.organization,
            journal_number='J001',
            journal_date=datetime.date(2025, 1, 15),
            period=self.period,
            journal_type=self.journal_type
        )
        response = self.client.get('/api/v1/journals/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_create_journal(self):
        """Test creating a new journal."""
        data = {
            'journal_number': 'J001',
            'journal_date': '2025-01-15',
            'period': self.period.id,
            'journal_type': self.journal_type.id
        }
        response = self.client.post('/api/v1/journals/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_retrieve_journal(self):
        """Test retrieving a specific journal."""
        journal = Journal.objects.create(
            organization=self.organization,
            journal_number='J001',
            journal_date=datetime.date(2025, 1, 15),
            period=self.period,
            journal_type=self.journal_type
        )
        response = self.client.get(f'/api/v1/journals/{journal.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['journal_number'], 'J001')
    
    def test_post_journal(self):
        """Test posting a journal."""
        journal = Journal.objects.create(
            organization=self.organization,
            journal_number='J001',
            journal_date=datetime.date(2025, 1, 15),
            period=self.period,
            journal_type=self.journal_type,
            is_posted=False
        )
        JournalLine.objects.create(
            journal=journal,
            line_number=1,
            account=self.debit_account,
            debit_amount=Decimal('100.00')
        )
        JournalLine.objects.create(
            journal=journal,
            line_number=2,
            account=self.credit_account,
            credit_amount=Decimal('100.00')
        )
        
        response = self.client.post(f'/api/v1/journals/{journal.id}/post/', {})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_get_journal_lines(self):
        """Test getting journal lines."""
        journal = Journal.objects.create(
            organization=self.organization,
            journal_number='J001',
            journal_date=datetime.date(2025, 1, 15),
            period=self.period,
            journal_type=self.journal_type
        )
        JournalLine.objects.create(
            journal=journal,
            line_number=1,
            account=self.debit_account,
            debit_amount=Decimal('100.00')
        )
        
        response = self.client.get(f'/api/v1/journals/{journal.id}/lines/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
    
    def test_filter_unposted_journals(self):
        """Test filtering unposted journals."""
        Journal.objects.create(
            organization=self.organization,
            journal_number='J001',
            journal_date=datetime.date(2025, 1, 15),
            period=self.period,
            journal_type=self.journal_type,
            is_posted=False
        )
        Journal.objects.create(
            organization=self.organization,
            journal_number='J002',
            journal_date=datetime.date(2025, 1, 16),
            period=self.period,
            journal_type=self.journal_type,
            is_posted=True
        )
        
        response = self.client.get('/api/v1/journals/unposted/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


# ============================================================================
# Report API Tests
# ============================================================================

class ReportAPITestCase(APITestCase):
    """Test Report REST API endpoints."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.organization = Organization.objects.create(name='Test Org')
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            organization=self.organization
        )
        self.client.force_authenticate(user=self.user)
        
        # Create accounts
        self.account = Account.objects.create(
            organization=self.organization,
            code='1000',
            name='Cash',
            account_type='ASSET'
        )
    
    def test_trial_balance_report(self):
        """Test trial balance report endpoint."""
        response = self.client.get('/api/v1/trial-balance/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('accounts', response.data)
    
    def test_general_ledger_report(self):
        """Test general ledger report endpoint."""
        response = self.client.get(f'/api/v1/general-ledger/?account_id={self.account.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('entries', response.data)


# ============================================================================
# Import/Export API Tests
# ============================================================================

class ImportExportAPITestCase(APITestCase):
    """Test Import/Export REST API endpoints."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.organization = Organization.objects.create(name='Test Org')
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            organization=self.organization
        )
        self.client.force_authenticate(user=self.user)
    
    def test_export_journals(self):
        """Test exporting journals."""
        response = self.client.get('/api/v1/export/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_import_journals(self):
        """Test importing journals (file upload)."""
        import io
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        # Create sample JSON data
        data = json.dumps({
            'journals': [
                {
                    'journal_number': 'J001',
                    'journal_date': '2025-01-15',
                    'lines': [
                        {'account_code': '1000', 'debit': '100.00'},
                        {'account_code': '3000', 'credit': '100.00'}
                    ]
                }
            ]
        })
        
        file = SimpleUploadedFile(
            'journals.json',
            data.encode('utf-8'),
            content_type='application/json'
        )
        
        response = self.client.post('/api/v1/import/', {'file': file}, format='multipart')
        # Should return success or validation error
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])


class BulkJournalActionViewTest(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Test Org')
        self.user = User.objects.create_user(username='testuser', password='password', organization=self.organization)
        self.client.force_authenticate(user=self.user)
        self.fiscal_year = FiscalYear.objects.create(
            organization=self.organization,
            code='FY2025',
            name='Fiscal Year 2025',
            start_date='2025-01-01',
            end_date='2025-12-31'
        )
        self.period = AccountingPeriod.objects.create(
            fiscal_year=self.fiscal_year,
            period_number=1,
            name='January',
            start_date='2025-01-01',
            end_date='2025-01-31'
        )
        self.journal_type = JournalType.objects.create(
            organization=self.organization,
            code='GJ',
            name='General Journal'
        )
        self.journal1 = Journal.objects.create(
            organization=self.organization,
            journal_number='J1',
            journal_date=datetime.date(2025, 1, 15),
            period=self.period,
            journal_type=self.journal_type
        )
        self.journal2 = Journal.objects.create(
            organization=self.organization,
            journal_number='J2',
            journal_date=datetime.date(2025, 1, 16),
            period=self.period,
            journal_type=self.journal_type
        )
        self.url = reverse('accounting:journal_bulk_action')

    def test_bulk_post_action(self):
        data = {
            'action': 'post',
            'journal_ids': [self.journal1.id, self.journal2.id]
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Successfully performed post on 2 journals.')

    def test_bulk_delete_action(self):
        data = {
            'action': 'delete',
            'journal_ids': [self.journal1.id, self.journal2.id]
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Successfully performed delete on 2 journals.')

    def test_missing_action(self):
        data = {
            'journal_ids': [self.journal1.id, self.journal2.id]
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Missing action or journal_ids')


class JournalWorkflowAPITests(APITestCase):
    def setUp(self):
        self.organization = fac.create_organization()
        self.user = fac.create_user(organization=self.organization, role="manager")
        self.client.force_authenticate(self.user)

        self.journal = fac.create_journal(
            organization=self.organization,
            created_by=self.user,
            total_debit=Decimal("200.00"),
            total_credit=Decimal("200.00"),
        )
        account = fac.create_chart_of_account(organization=self.organization)
        JournalLine.objects.create(
            journal=self.journal,
            line_number=1,
            account=account,
            debit_amount=Decimal("200.00"),
            credit_amount=Decimal("0"),
        )
        JournalLine.objects.create(
            journal=self.journal,
            line_number=2,
            account=account,
            debit_amount=Decimal("0"),
            credit_amount=Decimal("200.00"),
        )
        self.workflow = ApprovalWorkflow.objects.create(
            organization=self.organization,
            name="Default Journal",
            area="journal",
        )
        ApprovalStep.objects.create(
            workflow=self.workflow,
            sequence=1,
            role="manager",
            min_amount=0,
        )
        ConfigurationService.set_value(
            organization=self.organization,
            scope=ConfigurationEntry.SCOPE_FINANCE,
            key="approval_workflows",
            value={"journal": self.workflow.name},
            user=self.user,
        )

    def _submit(self):
        response = self.client.post(f'/api/v1/journals/{self.journal.journal_id}/submit/', {})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.journal.refresh_from_db()
        self.assertEqual(self.journal.status, 'awaiting_approval')

    def test_submit_creates_pending_task(self):
        self._submit()

    def test_approve_finalizes_workflow(self):
        self._submit()
        response = self.client.post(f'/api/v1/journals/{self.journal.journal_id}/approve/', {})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.journal.refresh_from_db()
        self.assertEqual(self.journal.status, 'approved')

    def test_reject_moves_journal_to_rejected(self):
        self._submit()
        response = self.client.post(
            f'/api/v1/journals/{self.journal.journal_id}/reject/',
            {'notes': 'Insufficient documentation'},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.journal.refresh_from_db()
        self.assertEqual(self.journal.status, 'rejected')

    def test_missing_journal_ids(self):
        data = {
            'action': 'post',
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Missing action or journal_ids')
