from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from accounting.models import Organization, Journal, JournalLine, AccountType, ChartOfAccount, JournalType, AccountingPeriod, FiscalYear

User = get_user_model()

class GeneralJournalTestCase(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Test Org')
        self.user = User.objects.create_user(username='testuser', password='password', organization=self.organization)
        self.account_type = AccountType.objects.create(name='Asset', nature='asset', classification='Current Asset', display_order=1)
        self.account = ChartOfAccount.objects.create(organization=self.organization, account_type=self.account_type, account_code='1000', account_name='Cash')
        self.fiscal_year = FiscalYear.objects.create(organization=self.organization, code='FY2024', name='Fiscal Year 2024', start_date='2024-01-01', end_date='2024-12-31')
        self.period = AccountingPeriod.objects.create(fiscal_year=self.fiscal_year, period_number=1, name='January', start_date='2024-01-01', end_date='2024-01-31')
        self.journal_type = JournalType.objects.create(organization=self.organization, code='GJ', name='General Journal')

    def test_journal_creation(self):
        journal = Journal.objects.create(
            organization=self.organization,
            journal_type=self.journal_type,
            period=self.period,
            journal_date='2024-01-15',
            description='Test Journal'
        )
        self.assertEqual(Journal.objects.count(), 1)
        self.assertEqual(journal.description, 'Test Journal')

    def test_journal_line_creation(self):
        journal = Journal.objects.create(
            organization=self.organization,
            journal_type=self.journal_type,
            period=self.period,
            journal_date='2024-01-15',
            description='Test Journal'
        )
        line = JournalLine.objects.create(
            journal=journal,
            line_number=1,
            account=self.account,
            debit_amount=100,
            credit_amount=0
        )
        self.assertEqual(JournalLine.objects.count(), 1)
        self.assertEqual(line.debit_amount, 100)

    def test_journal_view(self):
        self.client.login(username='testuser', password='password')
        response = self.client.get(reverse('accounting:journal_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounting/journal_list.html')