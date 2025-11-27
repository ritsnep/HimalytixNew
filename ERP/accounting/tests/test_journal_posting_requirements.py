from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounting.models import (
    AccountingPeriod,
    AccountType,
    Approval,
    ChartOfAccount,
    FiscalYear,
    Journal,
    JournalLine,
    JournalType,
)
from accounting.services.journal_entry_service import JournalEntryService
from accounting.services.posting_service import PostingService
from usermanagement.models import Organization


class JournalPostingRequirementsTests(TestCase):
    def setUp(self) -> None:
        self.organization = Organization.objects.create(name="Test Org", code="TEST", type="company")
        User = get_user_model()
        self.user = User.objects.create_user(
            username="poster",
            password="password",
            full_name="Poster",
            role="admin",
            organization=self.organization,
        )
        self.user.is_superuser = True
        self.user.save(update_fields=["is_superuser"])
        # Ensure PostingService pulls the expected organization context
        self.user.get_active_organization = lambda: self.organization

        self.fiscal_year = FiscalYear.objects.create(
            organization=self.organization,
            code="FY25",
            name="FY 2025",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_current=True,
            created_by=self.user,
        )
        self.period = AccountingPeriod.objects.create(
            fiscal_year=self.fiscal_year,
            period_number=1,
            name="Jan 2025",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            status="open",
            created_by=self.user,
        )

        self.account_type = AccountType.objects.create(
            code="EXP",
            name="Expense",
            nature="expense",
            classification="expense",
            display_order=1,
        )
        self.debit_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=self.account_type,
            account_code="5000",
            account_name="Expense Account",
            created_by=self.user,
        )
        self.credit_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=self.account_type,
            account_code="4000",
            account_name="Income Account",
            created_by=self.user,
        )

        self.requires_approval_type = JournalType.objects.create(
            organization=self.organization,
            code="APP",
            name="Needs Approval",
            requires_approval=True,
            auto_numbering_prefix="APP-",
            created_by=self.user,
            updated_by=self.user,
        )
        self.auto_number_type = JournalType.objects.create(
            organization=self.organization,
            code="AUT",
            name="Auto Number",
            requires_approval=False,
            auto_numbering_prefix="AUT-",
            created_by=self.user,
            updated_by=self.user,
        )

        self.service = JournalEntryService(self.user, self.organization)

    def _build_journal(self, journal_type: JournalType, status: str) -> Journal:
        journal = Journal.objects.create(
            organization=self.organization,
            journal_type=journal_type,
            period=self.period,
            journal_date=date(2025, 1, 15),
            status=status,
            currency_code="USD",
            exchange_rate=Decimal("1"),
            created_by=self.user,
            updated_by=self.user,
        )
        JournalLine.objects.create(
            journal=journal,
            line_number=1,
            account=self.debit_account,
            description="Debit",
            debit_amount=Decimal("100"),
            credit_amount=Decimal("0"),
            created_by=self.user,
            updated_by=self.user,
        )
        JournalLine.objects.create(
            journal=journal,
            line_number=2,
            account=self.credit_account,
            description="Credit",
            debit_amount=Decimal("0"),
            credit_amount=Decimal("100"),
            created_by=self.user,
            updated_by=self.user,
        )
        journal.update_totals()
        journal.save(update_fields=["total_debit", "total_credit"])
        return journal

    def test_requires_approval_status_gate(self) -> None:
        journal = self._build_journal(self.requires_approval_type, status="awaiting_approval")
        with self.assertRaisesMessage(ValueError, "requires approval before posting"):
            self.service.post(journal)

    def test_requires_approval_must_have_approval_record(self) -> None:
        journal = self._build_journal(self.requires_approval_type, status="approved")
        with self.assertRaisesMessage(ValueError, "Approval record is required"):
            self.service.post(journal)

        Approval.objects.create(journal=journal, approver=self.user)
        posted = self.service.post(journal)
        self.assertEqual(posted.status, "posted")

    def test_post_assigns_number_when_missing(self) -> None:
        journal = self._build_journal(self.auto_number_type, status="draft")
        Journal.objects.filter(pk=journal.pk).update(journal_number="")
        journal.refresh_from_db()

        # Use the current sequence value (which may have advanced during fixture creation)
        self.auto_number_type.refresh_from_db()
        next_seq = self.auto_number_type.sequence_next
        expected_number = f"{self.auto_number_type.auto_numbering_prefix or ''}{str(next_seq).zfill(self.auto_number_type.sequence_padding)}"

        posted = self.service.post(journal)
        self.assertEqual(posted.journal_number, expected_number)
        self.assertEqual(posted.status, "posted")

        self.auto_number_type.refresh_from_db()
        self.assertEqual(self.auto_number_type.sequence_next, next_seq + 1)

    def test_post_rejects_closed_period(self) -> None:
        journal = self._build_journal(self.auto_number_type, status="draft")
        self.period.status = "closed"
        self.period.save(update_fields=["status"])

        with self.assertRaisesMessage(ValueError, PostingService.ERR_PERIOD_CLOSED):
            self.service.post(journal)

    def test_post_rejects_date_outside_selected_period(self) -> None:
        journal = self._build_journal(self.auto_number_type, status="draft")
        Journal.objects.filter(pk=journal.pk).update(journal_date=date(2025, 2, 5))
        journal.refresh_from_db()

        with self.assertRaisesMessage(ValueError, PostingService.ERR_PERIOD_MISMATCH):
            self.service.post(journal)
