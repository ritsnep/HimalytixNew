from django.test import TestCase
from django.contrib.auth import get_user_model
from accounting.models import Journal, JournalLine, JournalType, VoucherModeConfig
from accounting.services.journal_entry_service import JournalEntryService
from usermanagement.models import Organization

User = get_user_model()

class JournalEntryServiceTest(TestCase):

    def setUp(self):
        self.organization = Organization.objects.create(name='Test Org')
        self.user = User.objects.create_user(username='testuser', password='password', organization=self.organization)
        self.journal_type = JournalType.objects.create(organization=self.organization, name='General Journal')
        self.service = JournalEntryService(self.user, self.organization)

    def test_create_journal_entry(self):
        journal_data = {
            'journal_type': self.journal_type,
            'description': 'Test Journal',
            'journal_date': '2025-01-01',
        }
        lines_data = [
            {'account_id': 1, 'debit_amount': 100, 'credit_amount': 0},
            {'account_id': 2, 'debit_amount': 0, 'credit_amount': 100},
        ]
        journal = self.service.create_journal_entry(journal_data, lines_data)
        self.assertEqual(journal.description, 'Test Journal')
        self.assertEqual(journal.lines.count(), 2)
        self.assertEqual(journal.total_debit, 100)
        self.assertEqual(journal.total_credit, 100)

    def test_update_journal_entry(self):
        journal = self.service.create_journal_entry(
            {'journal_type': self.journal_type, 'description': 'Old Journal', 'journal_date': '2025-01-01'},
            [{'account_id': 1, 'debit_amount': 100, 'credit_amount': 0}, {'account_id': 2, 'debit_amount': 0, 'credit_amount': 100}]
        )
        journal_data = {'description': 'New Journal'}
        lines_data = [
            {'account_id': 3, 'debit_amount': 200, 'credit_amount': 0},
            {'account_id': 4, 'debit_amount': 0, 'credit_amount': 200},
        ]
        updated_journal = self.service.update_journal_entry(journal, journal_data, lines_data)
        self.assertEqual(updated_journal.description, 'New Journal')
        self.assertEqual(updated_journal.lines.count(), 2)
        self.assertEqual(updated_journal.total_debit, 200)

    def test_validation(self):
        with self.assertRaises(ValueError):
            self.service.create_journal_entry({}, [])
        with self.assertRaises(ValueError):
            self.service.create_journal_entry(
                {'journal_type': self.journal_type, 'description': 'Test', 'journal_date': '2025-01-01'},
                [{'account_id': 1, 'debit_amount': 100, 'credit_amount': 50}]
            )

    def test_workflow(self):
        journal = self.service.create_journal_entry(
            {'journal_type': self.journal_type, 'description': 'Test', 'journal_date': '2025-01-01'},
            [{'account_id': 1, 'debit_amount': 100, 'credit_amount': 0}, {'account_id': 2, 'debit_amount': 0, 'credit_amount': 100}]
        )
        self.assertEqual(journal.status, 'draft')
        self.service.submit(journal)
        self.assertEqual(journal.status, 'awaiting_approval')
        self.service.approve(journal)
        self.assertEqual(journal.status, 'approved')
        self.service.post(journal)
        self.assertEqual(journal.status, 'posted')

    def test_permissions(self):
        # This test requires a more sophisticated setup with mock permissions
        # For now, we'll just test that the methods raise PermissionError
        with self.assertRaises(PermissionError):
            self.service.create_journal_entry({}, [])
        journal = Journal(organization=self.organization, journal_type=self.journal_type)
        with self.assertRaises(PermissionError):
            self.service.update_journal_entry(journal, {}, [])
        with self.assertRaises(PermissionError):
            self.service.submit(journal)
        with self.assertRaises(PermissionError):
            self.service.approve(journal)
        with self.assertRaises(PermissionError):
            self.service.reject(journal)
        with self.assertRaises(PermissionError):
            self.service.post(journal)
