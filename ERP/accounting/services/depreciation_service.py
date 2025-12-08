from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from django.db import transaction
from django.utils import timezone

from accounting.models import Asset, Journal, JournalLine
from accounting.services.posting_service import PostingService


@dataclass
class DepreciationEntry:
    asset: Asset
    amount: Decimal


class DepreciationService:
    """Generates depreciation journals for active assets."""

    def __init__(self, user, journal_type):
        self.user = user
        self.journal_type = journal_type
        self.posting_service = PostingService(user)

    def _calculate_amount(self, asset: Asset) -> Decimal:
        if asset.depreciation_method == 'straight_line':
            monthly = asset.cost - asset.salvage_value
            total_months = asset.useful_life_years * Decimal('12')
            return (monthly / total_months).quantize(Decimal('0.01'))
        elif asset.depreciation_method == 'declining_balance':
            book_value = asset.book_value
            rate = (Decimal('1') / asset.useful_life_years).quantize(Decimal('0.0001'))
            return (book_value * rate / Decimal('12')).quantize(Decimal('0.01'))
        raise ValueError("Unsupported depreciation method.")

    def gather_assets(self) -> Iterable[DepreciationEntry]:
        for asset in Asset.objects.filter(status='active', accumulated_depreciation__lt=asset.cost):
            amount = self._calculate_amount(asset)
            if amount > 0:
                yield DepreciationEntry(asset=asset, amount=amount)

    @transaction.atomic
    def post_period(self, period_date, expense_account, accumulated_account):
        journal = Journal.objects.create(
            organization=self.journal_type.organization,
            journal_type=self.journal_type,
            period=self.journal_type.organization.fiscal_years.filter(is_current=True).first().periods.filter(status='open').first(),
            journal_date=period_date,
            description=f"Depreciation for {period_date:%B %Y}",
            currency_code=getattr(self.journal_type.organization, 'base_currency_code_id', 'USD') or 'USD',
            exchange_rate=Decimal('1'),
            status='draft',
            created_by=self.user,
        )
        line_number = 1
        for entry in self.gather_assets():
            JournalLine.objects.create(
                journal=journal,
                line_number=line_number,
                account=expense_account,
                description=f"Depreciation - {entry.asset.name}",
                debit_amount=entry.amount,
                created_by=self.user,
            )
            line_number += 1
            JournalLine.objects.create(
                journal=journal,
                line_number=line_number,
                account=accumulated_account,
                description=f"Accumulated depreciation - {entry.asset.name}",
                credit_amount=entry.amount,
                created_by=self.user,
            )
            line_number += 1
            entry.asset.accumulated_depreciation += entry.amount
            entry.asset.save(update_fields=['accumulated_depreciation', 'updated_at'])
        posted = self.posting_service.post(journal)
        return posted
