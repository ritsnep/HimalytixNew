from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from accounting.models import AccountType, GeneralLedger, Journal, JournalLine, VoucherProcess
from accounting.services.create_voucher import create_voucher_transaction
from accounting.services.posting_service import PostingService
from accounting.services.voucher_errors import VoucherProcessError
from accounting.tests.factories import (
    create_accounting_period,
    create_chart_of_account,
    create_journal_type,
    create_organization,
    create_user,
    create_voucher_mode_config,
)
from inventory.models import Product, StockLedger, Warehouse


class VoucherTransactionSafetyTests(TestCase):
    def setUp(self):
        self.organization = create_organization()
        self.user = create_user(organization=self.organization)
        self.period = create_accounting_period(organization=self.organization)
        self.journal_type = create_journal_type(organization=self.organization, code="VT")

        asset_type = AccountType.objects.create(
            code="AT-100",
            name="Asset",
            nature=AccountType.Nature.ASSET,
            classification=AccountType.Classification.CURRENT,
            balance_sheet_category=AccountType.BalanceSheetCategory.ASSETS,
            income_statement_category=None,
            cash_flow_category=AccountType.CashFlowCategory.INVESTING,
            display_order=1,
        )
        expense_type = AccountType.objects.create(
            code="AT-200",
            name="Expense",
            nature=AccountType.Nature.EXPENSE,
            classification=AccountType.Classification.OPERATING,
            balance_sheet_category=None,
            income_statement_category=AccountType.IncomeStatementCategory.EXPENSE,
            cash_flow_category=AccountType.CashFlowCategory.OPERATING,
            display_order=2,
        )
        self.inventory_account = create_chart_of_account(
            organization=self.organization,
            account_type=asset_type,
            account_code="1400",
            account_name="Inventory",
        )
        self.cogs_account = create_chart_of_account(
            organization=self.organization,
            account_type=expense_type,
            account_code="5100",
            account_name="COGS",
        )

        self.warehouse = Warehouse.objects.create(
            organization=self.organization,
            code="MAIN",
            name="Main Warehouse",
            address_line1="123 Main",
            city="Kathmandu",
            country_code="NP",
        )
        self.product = Product.objects.create(
            organization=self.organization,
            code="PRD-TEST",
            name="Inventory Item",
            inventory_account=self.inventory_account,
            expense_account=self.cogs_account,
            is_inventory_item=True,
        )

    def test_inventory_failure_rolls_back_voucher_and_gl(self):
        config = create_voucher_mode_config(
            organization=self.organization,
            journal_type=self.journal_type,
            affects_inventory=True,
            affects_gl=True,
            schema_definition={
                "settings": {"inventory": {"txn_type": "issue"}},
                "header": [],
                "lines": [],
            },
        )

        header_data = {"journal_date": timezone.now().date(), "currency_code": "USD"}
        lines_data = [
            {
                "account": self.cogs_account.pk,
                "debit_amount": Decimal("100.00"),
                "product": self.product.pk,
                "warehouse": self.warehouse.pk,
                "quantity": Decimal("5"),
            },
            {
                "account": self.inventory_account.pk,
                "credit_amount": Decimal("100.00"),
            },
        ]

        with self.assertRaises(VoucherProcessError) as ctx:
            create_voucher_transaction(
                user=self.user,
                config_id=config.pk,
                header_data=header_data,
                lines_data=lines_data,
                commit_type="post",
            )

        self.assertEqual(ctx.exception.code, "INV-001")
        self.assertEqual(Journal.objects.count(), 0)
        self.assertEqual(JournalLine.objects.count(), 0)
        self.assertEqual(GeneralLedger.objects.count(), 0)
        self.assertEqual(StockLedger.objects.count(), 0)
        process = VoucherProcess.objects.first()
        self.assertIsNotNone(process)
        self.assertEqual(process.status, "failed")
        self.assertIsNone(process.journal_id)
        self.assertIsNotNone(process.journal_id_snapshot)

    def test_posting_is_idempotent(self):
        journal = Journal.objects.create(
            organization=self.organization,
            journal_type=self.journal_type,
            period=self.period,
            journal_date=timezone.now().date(),
            currency_code="USD",
            status="draft",
            created_by=self.user,
        )
        JournalLine.objects.bulk_create(
            [
                JournalLine(
                    journal=journal,
                    line_number=1,
                    account=self.cogs_account,
                    debit_amount=Decimal("75.00"),
                    credit_amount=Decimal("0"),
                ),
                JournalLine(
                    journal=journal,
                    line_number=2,
                    account=self.inventory_account,
                    debit_amount=Decimal("0"),
                    credit_amount=Decimal("75.00"),
                ),
            ]
        )

        posting_service = PostingService(self.user)
        journal = posting_service.post(journal)
        gl_count = GeneralLedger.objects.filter(journal=journal).count()

        posting_service.post(journal)
        self.assertEqual(GeneralLedger.objects.filter(journal=journal).count(), gl_count)
        self.assertEqual(StockLedger.objects.filter(reference_id=journal.journal_number).count(), 0)

    def test_inventory_requires_uom(self):
        config = create_voucher_mode_config(
            organization=self.organization,
            journal_type=self.journal_type,
            affects_inventory=True,
            affects_gl=True,
            schema_definition={
                "settings": {"inventory": {"txn_type": "issue"}},
                "header": [],
                "lines": [],
            },
        )

        header_data = {"journal_date": timezone.now().date(), "currency_code": "USD"}
        lines_data = [
            {
                "account": self.cogs_account.pk,
                "debit_amount": Decimal("10.00"),
                "product": self.product.pk,
                "warehouse": self.warehouse.pk,
                "quantity": Decimal("1"),
            },
            {
                "account": self.inventory_account.pk,
                "credit_amount": Decimal("10.00"),
            },
        ]

        with self.assertRaises(VoucherProcessError) as ctx:
            create_voucher_transaction(
                user=self.user,
                config_id=config.pk,
                header_data=header_data,
                lines_data=lines_data,
                commit_type="save",
            )

        self.assertEqual(ctx.exception.code, "INV-011")
