from decimal import Decimal

from django.forms import ValidationError
from django.test import TestCase

from accounting.models import (
    AccountingPeriod,
    AccountType,
    ChartOfAccount,
    Currency,
    CurrencyExchangeRate,
    FiscalYear,
    GeneralLedger,
    Journal,
    JournalLine,
    JournalType,
    Organization,
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
        self.assertEqual(num1, "GJ001")
        self.assertEqual(num2, "GJ002")

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

        posted_journal = post_journal(journal)

        journal.refresh_from_db()
        self.assertEqual(posted_journal.status, "posted")
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

    def test_post_journal_auto_exchange_rate_lookup(self):
        usd = Currency.objects.create(currency_code="USD", currency_name="US Dollar", symbol="$")
        eur = Currency.objects.create(currency_code="EUR", currency_name="Euro", symbol="€")
        self.org.base_currency_code = "USD"
        self.org.save(update_fields=["base_currency_code"])

        CurrencyExchangeRate.objects.create(
            organization=self.org,
            from_currency=eur,
            to_currency=usd,
            rate_date=self.period.start_date,
            exchange_rate=Decimal("1.200000"),
            source="test",
        )

        journal = Journal.objects.create(
            organization=self.org,
            journal_type=self.jt,
            period=self.period,
            journal_date=self.period.start_date,
            currency_code="EUR",
            exchange_rate=Decimal("0"),
            total_debit=Decimal("120"),
            total_credit=Decimal("120"),
        )
        JournalLine.objects.create(
            journal=journal,
            line_number=1,
            account=self.acc1,
            debit_amount=Decimal("120"),
            amount_txn=Decimal("100"),
            amount_base=Decimal("0"),
            fx_rate=Decimal("0"),
        )
        JournalLine.objects.create(
            journal=journal,
            line_number=2,
            account=self.acc2,
            credit_amount=Decimal("120"),
            amount_txn=Decimal("100"),
            amount_base=Decimal("0"),
            fx_rate=Decimal("0"),
        )

        post_journal(journal)

        journal.refresh_from_db()
        self.assertEqual(journal.exchange_rate, Decimal("1.200000"))
        self.assertEqual(journal.metadata.get("exchange_rate_source"), "test")
        line = journal.lines.get(line_number=1)
        self.assertEqual(line.amount_base, Decimal("120.0000"))
        self.assertEqual(line.fx_rate, Decimal("1.200000"))