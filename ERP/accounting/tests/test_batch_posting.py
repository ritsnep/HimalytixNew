from django.test import TestCase

from accounting.models import Journal, JournalLine
from accounting.services.batch_posting import BatchPostingService
from accounting.services.posting_service import OptimisticLockError, PostingService
from accounting.tests import factories as f


class BatchPostingServiceTests(TestCase):
    def setUp(self):
        self.organization = f.create_organization()
        self.user = f.create_user(organization=self.organization)
        self.account = f.create_chart_of_account(organization=self.organization)

    def _build_balanced_journal(self, organization=None, status="approved"):
        organization = organization or self.organization
        account = self.account if organization == self.organization else f.create_chart_of_account(organization=organization)
        journal = f.create_journal(
            organization=organization,
            status=status,
            journal_type=f.create_journal_type(organization=organization),
        )
        JournalLine.objects.create(
            journal=journal,
            line_number=1,
            account=account,
            debit_amount=100,
            credit_amount=0,
            functional_debit_amount=100,
            functional_credit_amount=0,
            description="Debit",
        )
        JournalLine.objects.create(
            journal=journal,
            line_number=2,
            account=account,
            debit_amount=0,
            credit_amount=100,
            functional_debit_amount=0,
            functional_credit_amount=100,
            description="Credit",
        )
        return journal

    def test_batch_posting_scopes_to_user_org(self):
        journal_in_org = self._build_balanced_journal()
        other_org = f.create_organization()
        other_journal = self._build_balanced_journal(organization=other_org)

        service = BatchPostingService(self.user)
        summary = service.post_journals(limit=10)

        self.assertIn(journal_in_org.pk, summary["posted"])
        self.assertNotIn(other_journal.pk, summary["posted"])

    def test_batch_posting_returns_failures(self):
        journal = f.create_journal(
            organization=self.organization,
            status="approved",
            journal_type=f.create_journal_type(organization=self.organization),
        )
        # Only create one line so journal is imbalanced.
        JournalLine.objects.create(
            journal=journal,
            line_number=1,
            account=self.account,
            debit_amount=100,
            credit_amount=0,
            functional_debit_amount=100,
            functional_credit_amount=0,
            description="Debit only",
        )

        service = BatchPostingService(self.user)
        summary = service.post_journals(limit=10)

        self.assertEqual(summary["posted"], [])
        self.assertEqual(summary["failed"][0]["journal_id"], journal.pk)


class PostingServiceOptimisticLockTests(TestCase):
    def setUp(self):
        self.organization = f.create_organization()
        self.user = f.create_user(organization=self.organization)
        self.account = f.create_chart_of_account(organization=self.organization)

    def _prepare_journal(self):
        journal = f.create_journal(
            organization=self.organization,
            status="approved",
            journal_type=f.create_journal_type(organization=self.organization),
        )
        JournalLine.objects.create(
            journal=journal,
            line_number=1,
            account=self.account,
            debit_amount=200,
            credit_amount=0,
            functional_debit_amount=200,
            functional_credit_amount=0,
            description="Debit",
        )
        JournalLine.objects.create(
            journal=journal,
            line_number=2,
            account=self.account,
            debit_amount=0,
            credit_amount=200,
            functional_debit_amount=0,
            functional_credit_amount=200,
            description="Credit",
        )
        return journal

    def test_posting_raises_when_rowversion_conflicts(self):
        journal = self._prepare_journal()
        stale_copy = Journal.objects.get(pk=journal.pk)
        service = PostingService(self.user)
        service.post(journal)

        with self.assertRaises(OptimisticLockError):
            PostingService(self.user).post(stale_copy)
