from django.test import TestCase

from accounting.models import JournalLine
from accounting.services.create_voucher import create_voucher
from accounting.services.posting_service import PostingService
from accounting.tests import factories as f
from accounting.tests import testhook_targets
from configuration.models import ConfigurationEntry
from configuration.services import ConfigurationService


class HookRunnerIntegrationTests(TestCase):
    """Ensure configured hooks fire for voucher and posting workflows."""

    def setUp(self):
        self.organization = f.create_organization()
        self.user = f.create_user(
            organization=self.organization,
            role="superadmin",
            is_superuser=True,
        )
        self.voucher_config = f.create_voucher_mode_config(organization=self.organization)
        self.account = f.create_chart_of_account(organization=self.organization)
        self.period = f.create_accounting_period(organization=self.organization)
        testhook_targets.reset()
        self.addCleanup(testhook_targets.reset)

    def _set_hooks(self, definitions):
        ConfigurationService.set_value(
            organization=self.organization,
            scope=ConfigurationEntry.SCOPE_FINANCE,
            key="accounting_hooks",
            value=definitions,
        )

    def _build_balanced_lines(self):
        return [
            {"account": self.account.pk, "debit_amount": "100.00", "credit_amount": "0"},
            {"account": self.account.pk, "debit_amount": "0", "credit_amount": "100.00"},
        ]

    def test_voucher_creation_emits_before_and_after_hooks(self):
        self._set_hooks(
            [
                {
                    "event": "before_voucher_save",
                    "path": "accounting.tests.testhook_targets.before_voucher_save_hook",
                    "enabled": True,
                },
                {
                    "event": "after_voucher_save",
                    "path": "accounting.tests.testhook_targets.after_voucher_save_hook",
                    "enabled": True,
                },
            ]
        )
        header_data = {"journal_date": self.period.start_date}

        journal = create_voucher(
            self.user,
            self.voucher_config.pk,
            header_data,
            self._build_balanced_lines(),
        )

        events = [event for event, _ in testhook_targets.recorded_events]
        self.assertEqual(events, ["before_voucher_save", "after_voucher_save"])

        before_context = testhook_targets.recorded_events[0][1]
        self.assertEqual(before_context["event"], "before_voucher_save")
        self.assertEqual(before_context["organization_id"], self.organization.pk)
        self.assertEqual(before_context["payload"]["config_id"], self.voucher_config.pk)

        after_context = testhook_targets.recorded_events[1][1]
        self.assertEqual(after_context["event"], "after_voucher_save")
        self.assertEqual(after_context["organization_id"], self.organization.pk)
        self.assertEqual(after_context["payload"]["journal_id"], journal.pk)

    def test_posting_emits_after_journal_post_hook(self):
        self._set_hooks(
            [
                {
                    "event": "after_journal_post",
                    "path": "accounting.tests.testhook_targets.after_journal_post_hook",
                    "enabled": True,
                }
            ]
        )
        journal = f.create_journal(
            organization=self.organization,
            journal_type=self.voucher_config.journal_type,
            period=self.period,
            created_by=self.user,
            status="draft",
            journal_date=self.period.start_date,
        )
        JournalLine.objects.create(
            journal=journal,
            line_number=1,
            account=self.account,
            debit_amount=100,
            credit_amount=0,
            functional_debit_amount=100,
            functional_credit_amount=0,
            description="Debit",
        )
        JournalLine.objects.create(
            journal=journal,
            line_number=2,
            account=self.account,
            debit_amount=0,
            credit_amount=100,
            functional_debit_amount=0,
            functional_credit_amount=100,
            description="Credit",
        )

        PostingService(self.user).post(journal)

        self.assertEqual(
            [event for event, _ in testhook_targets.recorded_events],
            ["after_journal_post"],
        )
        hook_context = testhook_targets.recorded_events[0][1]
        self.assertEqual(hook_context["payload"]["journal_id"], journal.pk)
        self.assertEqual(hook_context["organization_id"], self.organization.pk)
