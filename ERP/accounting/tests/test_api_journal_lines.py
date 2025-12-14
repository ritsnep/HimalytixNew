from django.test import TestCase
from rest_framework.test import APIClient
from django.urls import reverse
from django.utils import timezone

from accounting.models import Journal, JournalLine, JournalType, AccountingPeriod
from usermanagement.models import Organization
from django.contrib.auth import get_user_model


class JournalLineAPITest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser('admin', 'admin@example.com', 'pass')
        self.org = Organization.objects.create(code='TST', name='Test Org')
        self.user.organization = self.org
        self.user.save()

        # Create required journal type and accounting period
        jt = JournalType.objects.create(code='GJ', name='General')
        from accounting.models import FiscalYear
        fy = FiscalYear.objects.create(
            organization=self.org, code='FYTEST', name='FY Test', start_date=timezone.now().date(), end_date=timezone.now().date()
        )
        period = AccountingPeriod.objects.create(
            fiscal_year=fy, organization=self.org,
            period_number=1, name='P1', start_date=timezone.now().date(), end_date=timezone.now().date()
        )
        self.journal = Journal.objects.create(
            organization=self.org, journal_type=jt, period=period, journal_date=timezone.now().date()
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_create_journal_line_updates_totals(self):
        url = '/accounting/api/journal-lines/'
        data = {
            'journal': self.journal.pk,
            'line_number': 1,
            'account': None,
            'description': 'Test line',
            'debit_amount': '100.00',
            'credit_amount': '0.00',
        }
        # Create requires a valid account; use an existing ChartOfAccount if present
        from accounting.models import ChartOfAccount
        coa = ChartOfAccount.objects.filter(organization=self.org).first()
        if not coa:
            coa = ChartOfAccount.objects.create(organization=self.org, account_code='1000', account_name='Cash')
        data['account'] = coa.pk

        resp = self.client.post(url, data, format='json')
        self.assertIn(resp.status_code, (200, 201))
        self.journal.refresh_from_db()
        self.assertEqual(float(self.journal.total_debit), 100.00)
        self.assertFalse(self.journal.is_balanced)

    def test_update_and_delete_journal_line_adjusts_totals(self):
        # Create line
        from accounting.models import ChartOfAccount
        coa = ChartOfAccount.objects.filter(organization=self.org).first()
        if not coa:
            coa = ChartOfAccount.objects.create(organization=self.org, account_code='1000', account_name='Cash')

        line = JournalLine.objects.create(
            journal=self.journal, line_number=1, account=coa, debit_amount=200, credit_amount=0
        )
        self.journal.update_totals()
        self.journal.save()
        self.assertFalse(self.journal.is_balanced)

        # Update line to credit so balance becomes zero
        url = f'/accounting/api/journal-lines/{line.journal_line_id}/'
        resp = self.client.patch(url, {'debit_amount': '0.00', 'credit_amount': '200.00'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.journal.refresh_from_db()
        self.assertEqual(float(self.journal.total_debit), 0.00)
        self.assertEqual(float(self.journal.total_credit), 200.00)
        # Still not balanced
        self.assertFalse(self.journal.is_balanced)

        # Create balancing line via API
        resp2 = self.client.post('/accounting/api/journal-lines/', {
            'journal': self.journal.pk,
            'line_number': 2,
            'account': coa.pk,
            'debit_amount': '200.00',
            'credit_amount': '0.00'
        }, format='json')
        self.assertIn(resp2.status_code, (200,201))
        self.journal.refresh_from_db()
        self.assertTrue(self.journal.is_balanced)

        # Delete a line and ensure totals change
        del_resp = self.client.delete(f'/accounting/api/journal-lines/{line.journal_line_id}/')
        self.assertIn(del_resp.status_code, (204,200))
        self.journal.refresh_from_db()
        # After deletion, totals may differ
        self.assertNotEqual(float(self.journal.total_debit), float(self.journal.total_credit))
