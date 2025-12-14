from django.core.exceptions import ValidationError
from django.test import TestCase

from accounting.models import JournalLine
from accounting.services.document_lifecycle import DocumentLifecycleService, LifecycleTransitionError
from accounting.tests import factories as f
from configuration.services import ConfigurationService
from configuration.models import ConfigurationEntry


class DocumentLifecycleServiceTests(TestCase):
    def setUp(self):
        self.organization = f.create_organization()
        self.user = f.create_user(organization=self.organization)
        self.journal = f.create_journal(
            organization=self.organization,
            created_by=self.user,
            total_debit=100,
            total_credit=100,
        )
        account = f.create_chart_of_account(organization=self.organization)
        JournalLine.objects.create(
            journal=self.journal,
            line_number=1,
            account=account,
            debit_amount=100,
            credit_amount=0,
            functional_debit_amount=100,
            functional_credit_amount=0,
            description="Test debit",
        )
        JournalLine.objects.create(
            journal=self.journal,
            line_number=2,
            account=account,
            debit_amount=0,
            credit_amount=100,
            functional_debit_amount=0,
            functional_credit_amount=100,
            description="Test credit",
        )
        self.service = DocumentLifecycleService(journal=self.journal, acting_user=self.user)

    def test_happy_path_to_posted(self):
        self.service.transition("awaiting_approval")
        self.assertEqual(self.journal.status, "awaiting_approval")

        self.service.transition("approved")
        self.assertEqual(self.journal.status, "approved")
        self.assertIsNotNone(self.journal.approved_at)

        self.service.transition("posted")
        self.assertEqual(self.journal.status, "posted")
        self.assertTrue(self.journal.is_locked)
        self.assertEqual(self.journal.posted_by, self.user)

    def test_invalid_transition_rejected(self):
        with self.assertRaises(LifecycleTransitionError):
            self.service.transition("reversed")

    def test_validation_failure_blocks_posting(self):
        self.journal.total_debit = 50
        with self.assertRaises(ValidationError):
            self.service.transition("awaiting_approval")

    def test_configuration_can_override_transitions(self):
        ConfigurationService.set_value(
            organization=self.organization,
            scope=ConfigurationEntry.SCOPE_FINANCE,
            key="journal_lifecycle_transitions",
            value={"draft": ["approved"], "approved": ["posted"]},
        )
        self.service.transition("approved")
        self.assertEqual(self.journal.status, "approved")
