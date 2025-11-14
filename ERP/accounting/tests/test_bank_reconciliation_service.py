from datetime import date
from decimal import Decimal

from django.test import TestCase

from accounting.models import (
    AccountType,
    BankAccount,
    BankStatement,
    BankStatementLine,
    BankTransaction,
    ChartOfAccount,
    Currency,
    Organization,
)
from accounting.services.bank_reconciliation_service import BankReconciliationService


class BankReconciliationServiceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name='Reconcile Org',
            code='RECON',
            type='company',
        )
        self.currency = Currency.objects.create(
            currency_code='USD',
            currency_name='US Dollar',
            symbol='$',
        )
        bank_type = AccountType.objects.create(
            code='AST101',
            name='Bank',
            nature='asset',
            classification='Statement of Financial Position',
            balance_sheet_category='Assets',
            income_statement_category=None,
            cash_flow_category='Operating Activities',
            display_order=1,
        )
        self.bank_account = ChartOfAccount.objects.create(
            organization=self.org,
            account_type=bank_type,
            account_code='1011',
            account_name='Bank Account',
            currency=self.currency,
        )
        self.bank_master = BankAccount.objects.create(
            organization=self.org,
            bank_name='Main Bank',
            account_name='Operating',
            account_number='111222333',
            account_type='checking',
            currency=self.currency,
            current_balance=Decimal('1000'),
        )
        self.statement = BankStatement.objects.create(
            bank_account=self.bank_master,
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31),
        )

    def test_statement_line_matches_transaction(self):
        trx = BankTransaction.objects.create(
            bank_account=self.bank_master,
            transaction_date=date(2025, 1, 15),
            transaction_type='receipt',
            amount=Decimal('250'),
        )
        BankStatementLine.objects.create(
            statement=self.statement,
            line_date=date(2025, 1, 15),
            description='Deposit',
            amount=Decimal('250'),
        )
        service = BankReconciliationService(self.statement)
        matched = service.match()
        self.assertEqual(matched, 1)
        trx.refresh_from_db()
        self.assertTrue(trx.is_reconciled)
        line = self.statement.lines.first()
        self.assertIsNotNone(line.matched_transaction)

    def test_no_match_when_amount_differs(self):
        BankTransaction.objects.create(
            bank_account=self.bank_master,
            transaction_date=date(2025, 1, 15),
            transaction_type='payment',
            amount=Decimal('300'),
        )
        BankStatementLine.objects.create(
            statement=self.statement,
            line_date=date(2025, 1, 15),
            description='Withdrawal',
            amount=Decimal('250'),
        )
        service = BankReconciliationService(self.statement)
        matched = service.match()
        self.assertEqual(matched, 0)
        self.assertEqual(self.statement.status, 'draft')
