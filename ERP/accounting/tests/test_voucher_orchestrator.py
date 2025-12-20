from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from accounting.models import GeneralLedger, JournalLine, VoucherProcess
from accounting.services.voucher_orchestrator import VoucherOrchestrator
from accounting.services.voucher_errors import VoucherProcessError
from accounting.tests.factories import (
    create_account_type,
    create_accounting_period,
    create_chart_of_account,
    create_journal,
    create_journal_type,
    create_organization,
    create_user,
    create_voucher_mode_config,
)


class VoucherOrchestratorTests(TestCase):
    def setUp(self):
        self.organization = create_organization()
        self.user = create_user(organization=self.organization)
        self.period = create_accounting_period(organization=self.organization)
        self.journal_type = create_journal_type(organization=self.organization, code="VT")
        self.config = create_voucher_mode_config(
            organization=self.organization,
            journal_type=self.journal_type,
            affects_inventory=False,
            affects_gl=True,
        )
        asset_type = create_account_type(nature="asset")
        expense_type = create_account_type(nature="expense")
        self.asset_account = create_chart_of_account(
            organization=self.organization,
            account_type=asset_type,
            account_code="1400",
            account_name="Asset",
        )
        self.expense_account = create_chart_of_account(
            organization=self.organization,
            account_type=expense_type,
            account_code="5100",
            account_name="Expense",
        )

    def _make_journal(self):
        journal = create_journal(
            organization=self.organization,
            journal_type=self.journal_type,
            period=self.period,
            status="draft",
            created_by=self.user,
            journal_date=timezone.now().date(),
        )
        JournalLine.objects.bulk_create(
            [
                JournalLine(
                    journal=journal,
                    line_number=1,
                    account=self.expense_account,
                    debit_amount=Decimal("100.00"),
                    credit_amount=Decimal("0.00"),
                ),
                JournalLine(
                    journal=journal,
                    line_number=2,
                    account=self.asset_account,
                    debit_amount=Decimal("0.00"),
                    credit_amount=Decimal("100.00"),
                ),
            ]
        )
        return journal

    def test_post_idempotent_by_key(self):
        journal = self._make_journal()
        orchestrator = VoucherOrchestrator(self.user)
        orchestrator.process(journal.pk, commit_type="post", actor=self.user, idempotency_key="KEY-1", config=self.config)
        gl_count = GeneralLedger.objects.filter(journal=journal).count()

        orchestrator.process(journal.pk, commit_type="post", actor=self.user, idempotency_key="KEY-1", config=self.config)
        self.assertEqual(GeneralLedger.objects.filter(journal=journal).count(), gl_count)

        attempts = VoucherProcess.objects.filter(journal=journal, idempotency_key="KEY-1", status="succeeded")
        self.assertTrue(attempts.exists())

    def test_concurrent_processing_blocked(self):
        journal = self._make_journal()
        VoucherProcess.objects.create(
            journal=journal,
            organization=self.organization,
            actor=self.user,
            status="processing",
            saved_status="done",
            journal_status="done",
            gl_status="in_progress",
            inventory_status="pending",
        )
        orchestrator = VoucherOrchestrator(self.user)
        with self.assertRaises(VoucherProcessError) as exc:
            orchestrator.process(journal.pk, commit_type="post", actor=self.user, idempotency_key="KEY-2", config=self.config)
        self.assertEqual(exc.exception.code, "VCH-409")
