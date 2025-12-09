from decimal import Decimal
from typing import Iterable, Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounting.models import (
    AccountingPeriod,
    ExpenseEntry,
    ExpenseCategory,
    JournalType,
)
from accounting.services.journal_entry_service import JournalEntryService


class ExpenseEntryService:
    """Business logic for creating lightweight expense entries."""

    def __init__(self, user, organization):
        self.user = user
        self.organization = organization
        self._journal_service = JournalEntryService(user, organization)

    def create_expense_entry(
        self,
        category: ExpenseCategory,
        entry_date: Optional[timezone.datetime] = None,
        amount: Decimal = Decimal('0'),
        payment_account=None,
        paid_via='bank',
        description=None,
        reference=None,
        gst_applicable=False,
        gst_amount: Decimal = Decimal('0'),
        journal_type: Optional[JournalType] = None,
        attachments: Optional[Iterable] = None,
    ) -> ExpenseEntry:
        amount = Decimal(amount)
        gst_amount = Decimal(gst_amount)
        period = self._find_period(entry_date or timezone.now().date())
        journal_type = journal_type or self._get_default_journal_type()
        journal_data = {
            'journal_type': journal_type,
            'period': period,
            'journal_date': entry_date or timezone.now().date(),
            'description': description or f"{category.name} expense",
            'reference': reference,
        }
        debit_description = description or f"Expense: {category.name}"
        credit_description = f"Paid via {paid_via.capitalize()}"
        lines_data = [
            {
                'line_number': 1,
                'account': category.expense_account,
                'description': debit_description,
                'debit_amount': amount,
            },
            {
                'line_number': 2,
                'account': payment_account,
                'description': credit_description,
                'credit_amount': amount,
            },
        ]
        attachments = list(attachments or [])
        journal = self._journal_service.create_journal_entry(
            journal_data,
            lines_data,
            attachments=attachments if attachments else None,
        )
        expense_entry = ExpenseEntry.objects.create(
            organization=self.organization,
            category=category,
            journal=journal,
            journal_type=journal_type,
            payment_account=payment_account,
            entry_date=journal.journal_date,
            description=description or '',
            reference=reference or '',
            amount=amount,
            gst_applicable=gst_applicable,
            gst_amount=gst_amount,
            paid_via=paid_via,
            created_by=self.user,
            updated_by=self.user,
        )
        return expense_entry

    def _find_period(self, target_date):
        period = AccountingPeriod.objects.filter(
            organization=self.organization,
            start_date__lte=target_date,
            end_date__gte=target_date,
            status__in=['open', 'adjustment'],
        ).order_by('start_date').first()
        if not period:
            raise ValidationError("No open accounting period found for the selected date.")
        return period

    def _get_default_journal_type(self):
        candidate = JournalType.objects.filter(
            organization=self.organization,
            code__icontains='expense',
        ).first()
        if not candidate:
            candidate = JournalType.objects.filter(organization=self.organization).first()
        if not candidate:
            raise ValidationError("A journal type must be configured before recording expenses.")
        return candidate
