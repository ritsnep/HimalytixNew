from django.forms import ValidationError
from django.test import TestCase
from accounting.models import (
    FiscalYear,
    AccountingPeriod,
    Organization,
    AccountType,
    ChartOfAccount,
    JournalType,
    Journal,
    JournalLine,
    GeneralLedger,
    VoucherModeConfig,
)
from accounting.services import post_journal

class FiscalYearModelTest(TestCase):
    def test_str(self):
        fy = FiscalYear(code='FY24', name='2024', start_date='2024-01-01', end_date='2024-12-31')
        self.assertEqual(str(fy), 'FY24 - 2024')


class JournalTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Org", code="ORG", type="company")
        self.fy = FiscalYear.objects.create(
            organization=self.org,
            code="FY24",
            name="2024",
            start_date="2024-01-01",
            end_date="2024-12-31",
        )
        self.period = AccountingPeriod.objects.create(
            fiscal_year=self.fy,
            period_number=1,
            name="P1",
            start_date="2024-01-01",
            end_date="2024-01-31",
        )
        self.acc_type = AccountType.objects.create(
            code="AST001",
            name="Cash",
            nature="asset",
            classification="current",
            display_order=1,
        )
        self.acc1 = ChartOfAccount.objects.create(
            organization=self.org,
            account_type=self.acc_type,
            account_code="1000",
            account_name="Cash",
        )
        self.acc2 = ChartOfAccount.objects.create(
            organization=self.org,
            account_type=self.acc_type,
            account_code="2000",
            account_name="Receivable",
        )
        self.jt = JournalType.objects.create(
            organization=self.org,
            code="GJ",
            name="General Journal",
            auto_numbering_prefix="GJ",
        )

    def test_journal_type_sequence(self):
        num1 = self.jt.get_next_journal_number(self.period)
        num2 = self.jt.get_next_journal_number(self.period)
        self.assertEqual(num1, "GJ1")
        self.assertEqual(num2, "GJ2")

    def test_post_journal_creates_gl(self):
        journal = Journal.objects.create(
            organization=self.org,
            journal_type=self.jt,
            period=self.period,
            journal_date="2024-01-15",
            journal_number="",
            total_debit=100,
            total_credit=100,
        )
        JournalLine.objects.create(journal=journal, line_number=1, account=self.acc1, debit_amount=100)
        JournalLine.objects.create(journal=journal, line_number=2, account=self.acc2, credit_amount=100)

        post_journal(journal)

        self.assertEqual(journal.status, "posted")
        self.assertEqual(GeneralLedger.objects.filter(journal=journal).count(), 2)
        self.acc1.refresh_from_db()
        self.acc2.refresh_from_db()
        self.assertEqual(self.acc1.current_balance, 100)
        self.assertEqual(self.acc2.current_balance, -100)
        
    def test_default_voucher_config_created(self):
        jt2 = JournalType.objects.create(
            organization=self.org,
            code="SA",
            name="Sales",
        )
        self.assertTrue(
            VoucherModeConfig.objects.filter(journal_type=jt2, organization=self.org).exists()
        )

    def test_post_journal_fails_when_line_totals_mismatch(self):
        journal = Journal.objects.create(
            organization=self.org,
            journal_type=self.jt,
            period=self.period,
            journal_date="2024-01-15",
            journal_number="",
            total_debit=100,
            total_credit=100,
        )
        JournalLine.objects.create(journal=journal, line_number=1, account=self.acc1, debit_amount=80)
        JournalLine.objects.create(journal=journal, line_number=2, account=self.acc2, credit_amount=100)

        with self.assertRaises(ValidationError):
            post_journal(journal)