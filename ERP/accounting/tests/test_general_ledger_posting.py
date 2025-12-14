from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounting.models import GeneralLedger, JournalLine
from accounting.services.posting_service import PostingService
from accounting.tests import factories as f


class GeneralLedgerPostingTests(TestCase):
    def setUp(self):
        self.organization = f.create_organization()
        self.user = f.create_user(organization=self.organization, role="superadmin")
        # PostingService expects this helper for permission/tenant enforcement.
        self.user.get_active_organization = lambda: self.organization

        self.journal = f.create_journal(
            organization=self.organization,
            created_by=self.user,
            journal_number=None,
        )
        self.journal.journal_date = self.journal.period.start_date
        self.journal.save()
        self._add_balanced_lines()

    def _add_balanced_lines(self):
        account = f.create_chart_of_account(organization=self.organization)
        JournalLine.objects.create(
            journal=self.journal,
            line_number=1,
            account=account,
            description="Debit line",
            debit_amount=Decimal("100.00"),
            credit_amount=Decimal("0"),
        )
        JournalLine.objects.create(
            journal=self.journal,
            line_number=2,
            account=account,
            description="Credit line",
            debit_amount=Decimal("0"),
            credit_amount=Decimal("100.00"),
        )

    def test_post_creates_one_gl_entry_per_line(self):
        PostingService(self.user).post(self.journal)

        gl_entries = GeneralLedger.objects.filter(journal=self.journal).order_by("journal_line__line_number")
        self.assertEqual(gl_entries.count(), 2)
        self.assertTrue(all(entry.organization_id == self.organization.pk for entry in gl_entries))

    def test_reposting_same_lines_detects_duplicate_gl(self):
        PostingService(self.user).post(self.journal)

        # Simulate an accidental status change back to draft without cleaning GL entries.
        self.journal.refresh_from_db()
        self.journal.status = "draft"
        self.journal.is_locked = False
        self.journal.posted_at = None
        self.journal.save(update_fields=["status", "is_locked", "posted_at"])

        with self.assertRaises(ValidationError) as exc:
            PostingService(self.user).post(self.journal)
        self.assertIn("general ledger entry already exists", str(exc.exception).lower())
