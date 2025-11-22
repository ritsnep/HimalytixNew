import csv
from datetime import date
from io import StringIO

from django.test import TestCase, Client
from django.urls import reverse

from accounting.models import Journal, JournalLine
from accounting.tests import factories

class JournalImportTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        from django.conf import settings
        settings.CRISPY_TEMPLATE_PACK = 'bootstrap4'
        self.organization = factories.create_organization(name="Test Org")
        self.user = factories.create_user(organization=self.organization, username='testuser', password='password', role='superadmin')
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        content_type = ContentType.objects.get_for_model(Journal)
        permission = Permission.objects.get(content_type=content_type, codename='add_journal')
        self.user.user_permissions.add(permission)
        self.client.login(username='testuser', password='password')

        # Basic setup for a valid import
        self.currency = factories.create_currency(code='USD', name='US Dollar')
        self.journal_type = factories.create_journal_type(code='GJ', name='General Journal', organization=self.organization)
        self.account_type_asset = factories.create_account_type(code='AST', name='Asset', nature='asset')
        self.account1 = factories.create_chart_of_account(
            organization=self.organization,
            account_type=self.account_type_asset,
            account_code='1010',
            account_name='Cash',
        )
        self.account_type_liability = factories.create_account_type(code='LIA', name='Liability', nature='liability')
        self.account2 = factories.create_chart_of_account(
            organization=self.organization,
            account_type=self.account_type_liability,
            account_code='2010',
            account_name='Accounts Payable',
        )
        current_year = date.today().year
        self.fiscal_year = factories.create_fiscal_year(
            organization=self.organization,
            code=f'FY{current_year}',
            name=f'Fiscal Year {current_year}',
            start_date=date(current_year, 1, 1),
            end_date=date(current_year, 12, 31),
            is_current=True,
        )
        self.period = factories.create_accounting_period(
            fiscal_year=self.fiscal_year,
            period_number=date.today().month,
            name=f"Period {date.today().month}",
            start_date=date.today().replace(day=1),
            end_date=date.today().replace(day=28),
            status='open',
        )

    def test_journal_import_view_get(self):
        response = self.client.get(reverse('accounting:journal_import'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounting/journal_import.html')
        self.assertIn('form', response.context)

    def test_download_template_view(self):
        response = self.client.get(reverse('accounting:download_journal_import_template'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertTrue(response['Content-Disposition'].startswith('attachment; filename='))

    def _create_csv_file(self, data):
        """Helper to create an in-memory CSV file."""
        output = StringIO()
        writer = csv.writer(output)
        writer.writerows(data)
        output.seek(0)
        return output

    def test_successful_journal_import(self):
        csv_data = [
            ['grouping_key', 'journal_date', 'journal_type_code', 'journal_reference', 'journal_description', 'currency_code', 'exchange_rate', 'account_code', 'line_description', 'debit_amount', 'credit_amount', 'department_code', 'project_code', 'cost_center_code'],
            ['BATCH-01', '2025-08-05', 'GJ', 'REF-01', 'Test Journal 1', 'USD', '1.0', '1010', 'Debit cash', '100.00', '0.00', '', '', ''],
            ['BATCH-01', '2025-08-05', 'GJ', 'REF-01', 'Test Journal 1', 'USD', '1.0', '2010', 'Credit AP', '0.00', '100.00', '', '', '']
        ]
        csv_file = self._create_csv_file(csv_data)
        csv_file.name = 'test.csv'

        response = self.client.post(reverse('accounting:journal_import'), {'file': csv_file})

        self.assertEqual(response.status_code, 302) # Redirect on success
        self.assertEqual(Journal.objects.count(), 1)
        self.assertEqual(JournalLine.objects.count(), 2)
        journal = Journal.objects.first()
        self.assertEqual(journal.total_debit(), 100)
        self.assertEqual(journal.total_credit(), 100)

    def test_import_with_unbalanced_journal(self):
        csv_data = [
            ['grouping_key', 'journal_date', 'journal_type_code', 'journal_reference', 'journal_description', 'currency_code', 'exchange_rate', 'account_code', 'line_description', 'debit_amount', 'credit_amount', 'department_code', 'project_code', 'cost_center_code'],
            ['BATCH-02', '2025-08-05', 'GJ', 'REF-02', 'Unbalanced', 'USD', '1.0', '1010', 'Debit', '100.00', '0.00', '', '', ''],
            ['BATCH-02', '2025-08-05', 'GJ', 'REF-02', 'Unbalanced', 'USD', '1.0', '2010', 'Credit', '0.00', '99.00', '', '', '']
        ]
        csv_file = self._create_csv_file(csv_data)
        csv_file.name = 'test_unbalanced.csv'

        response = self.client.post(reverse('accounting:journal_import'), {'file': csv_file})
        
        self.assertEqual(response.status_code, 200) # Stays on the same page
        self.assertEqual(Journal.objects.count(), 0)
        messages = list(response.context['messages'])
        self.assertTrue(any("does not equal total credit" in str(m) for m in messages))

    def test_import_with_invalid_account_code(self):
        csv_data = [
            ['grouping_key', 'journal_date', 'journal_type_code', 'journal_reference', 'journal_description', 'currency_code', 'exchange_rate', 'account_code', 'line_description', 'debit_amount', 'credit_amount', 'department_code', 'project_code', 'cost_center_code'],
            ['BATCH-03', '2025-08-05', 'GJ', 'REF-03', 'Invalid Account', 'USD', '1.0', '9999', 'Debit', '100.00', '0.00', '', '', ''],
            ['BATCH-03', '2025-08-05', 'GJ', 'REF-03', 'Invalid Account', 'USD', '1.0', '2010', 'Credit', '0.00', '100.00', '', '', '']
        ]
        csv_file = self._create_csv_file(csv_data)
        csv_file.name = 'test_invalid_account.csv'

        response = self.client.post(reverse('accounting:journal_import'), {'file': csv_file})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Journal.objects.count(), 0)
        messages = list(response.context['messages'])
        self.assertTrue(any("Account with code '9999' not found" in str(m) for m in messages))

    def test_import_with_missing_required_header(self):
        csv_data = [
            ['grouping_key', 'journal_date'], # Missing many headers
            ['BATCH-04', '2025-08-05']
        ]
        csv_file = self._create_csv_file(csv_data)
        csv_file.name = 'test_missing_header.csv'

        response = self.client.post(reverse('accounting:journal_import'), {'file': csv_file})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Journal.objects.count(), 0)
        messages = list(response.context['messages'])
        self.assertTrue(any("CSV header mismatch" in str(m) for m in messages))