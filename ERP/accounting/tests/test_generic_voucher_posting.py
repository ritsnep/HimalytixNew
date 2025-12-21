from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounting.models import VoucherModeConfig, Journal
from accounting.services.create_voucher import create_voucher_transaction
from accounting.services.voucher_orchestrator import VoucherOrchestrator
from accounting.services.voucher_errors import VoucherProcessError
from accounting.voucher_schema import ui_schema_to_definition
from accounting.tests.factories import (
    create_accounting_period,
    create_chart_of_account,
    create_journal_type,
    create_organization,
)


class GenericVoucherPostingTests(TestCase):
    def setUp(self):
        self.organization = create_organization()
        self.period = create_accounting_period(organization=self.organization)
        self.journal_type = create_journal_type(organization=self.organization)
        self.account = create_chart_of_account(organization=self.organization)

        User = get_user_model()
        self.user = User.objects.create_user(
            username="user1",
            email="user1@example.com",
            password="pass12345",
        )
        if hasattr(self.user, "organization"):
            self.user.organization = self.organization
            self.user.save(update_fields=["organization"])

        ui_schema = {
            "header": {
                "journal_date": {"type": "date", "label": "Date", "required": True},
                "currency_code": {"type": "char", "label": "Currency", "required": True},
            },
            "lines": {
                "account": {"type": "select", "label": "Account", "required": True, "choices": "ChartOfAccount"},
                "debit_amount": {"type": "decimal", "label": "Debit", "required": False},
                "credit_amount": {"type": "decimal", "label": "Credit", "required": False},
            },
        }

        self.config = VoucherModeConfig.objects.create(
            code="UT-JOURNAL",
            name="UT Journal",
            organization=self.organization,
            module="accounting",
            journal_type=self.journal_type,
            schema_definition=ui_schema_to_definition(ui_schema),
            is_active=True,
        )

    def test_idempotent_create_reuses_journal(self):
        idempotency_key = "idempotent-key-1"
        header = {
            "journal_date": timezone.now().date().isoformat(),
            "currency_code": "USD",
        }
        lines = [
            {"account": self.account.pk, "debit_amount": "10", "credit_amount": "0"},
        ]
        voucher = create_voucher_transaction(
            user=self.user,
            config_id=self.config.pk,
            header_data=header,
            lines_data=lines,
            commit_type="save",
            idempotency_key=idempotency_key,
        )
        self.assertEqual(Journal.objects.count(), 1)

        lines2 = [
            {"account": self.account.pk, "debit_amount": "5", "credit_amount": "0"},
        ]
        voucher2 = create_voucher_transaction(
            user=self.user,
            config_id=self.config.pk,
            header_data=header,
            lines_data=lines2,
            commit_type="save",
            idempotency_key=idempotency_key,
        )
        self.assertEqual(Journal.objects.count(), 1)
        self.assertEqual(voucher.pk, voucher2.pk)

    def test_post_requires_approval_when_status_awaiting(self):
        header = {
            "journal_date": timezone.now().date().isoformat(),
            "currency_code": "USD",
        }
        lines = [
            {"account": self.account.pk, "debit_amount": "10", "credit_amount": "0"},
        ]
        voucher = create_voucher_transaction(
            user=self.user,
            config_id=self.config.pk,
            header_data=header,
            lines_data=lines,
            commit_type="submit",
            idempotency_key="approve-key",
        )
        self.assertEqual(voucher.status, "awaiting_approval")

        with mock.patch("accounting.services.voucher_orchestrator.PermissionUtils.has_permission", return_value=False):
            with self.assertRaises(VoucherProcessError) as ctx:
                VoucherOrchestrator(self.user).process(voucher_id=voucher.pk, commit_type="post", actor=self.user)
        self.assertEqual(ctx.exception.code, "VCH-403")

    def test_post_uses_posting_service(self):
        header = {
            "journal_date": timezone.now().date().isoformat(),
            "currency_code": "USD",
        }
        lines = [
            {"account": self.account.pk, "debit_amount": "10", "credit_amount": "0"},
            {"account": self.account.pk, "debit_amount": "0", "credit_amount": "10"},
        ]
        voucher = create_voucher_transaction(
            user=self.user,
            config_id=self.config.pk,
            header_data=header,
            lines_data=lines,
            commit_type="save",
            idempotency_key="post-key",
        )

        with mock.patch("accounting.services.voucher_orchestrator.PostingService") as posting_service:
            with mock.patch("accounting.services.voucher_orchestrator.PermissionUtils.has_permission", return_value=True):
                posting_service.return_value.post.return_value = voucher
                VoucherOrchestrator(self.user).process(voucher_id=voucher.pk, commit_type="post", actor=self.user)
                posting_service.return_value.post.assert_called()
