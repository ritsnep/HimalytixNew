from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Optional

from django.db import transaction

from accounting.models import Journal, JournalLine, JournalType, AccountingPeriod
from accounting.services.posting_service import PostingService
from enterprise.models import FixedAsset, FixedAssetCategory, AssetDepreciationSchedule


class FixedAssetPostingError(Exception):
    """Raised when required posting configuration is missing."""


@dataclass
class DepreciationEntry:
    asset: FixedAsset
    amount: Decimal


class FixedAssetService:
    """Posts acquisition/disposal and depreciation journals for enterprise assets."""

    def __init__(self, user, org):
        self.user = user
        self.org = org
        self.posting_service = PostingService(user)

    def _get_period(self, as_of: date) -> AccountingPeriod:
        period = (
            AccountingPeriod.objects.filter(
                organization=self.org,
                start_date__lte=as_of,
                end_date__gte=as_of,
                status="open",
            )
            .order_by("-start_date")
            .first()
        )
        if not period:
            raise FixedAssetPostingError("No open accounting period for the given date.")
        return period

    def _get_journal_type(self, code_or_name: str = "Adjustment Journal") -> JournalType:
        jt = (
            JournalType.objects.filter(organization=self.org, code=code_or_name)
            | JournalType.objects.filter(organization=self.org, name=code_or_name)
        ).first()
        if not jt:
            raise FixedAssetPostingError(
                f"JournalType '{code_or_name}' not found for organization {self.org}."
            )
        return jt

    def _ensure_accounts(self, category: FixedAssetCategory):
        if not (
            category.asset_account
            and category.depreciation_expense_account
            and category.accumulated_depreciation_account
        ):
            raise FixedAssetPostingError(
                f"Category {category.name} is missing required asset/expense/accumulated accounts."
            )

    @transaction.atomic
    def post_acquisition(self, asset: FixedAsset, as_of: Optional[date] = None):
        """Debit asset account, credit suspense/clearing (uses asset_account for both if no clearing is set)."""
        self._ensure_accounts(asset.category)
        as_of = as_of or asset.acquisition_date
        period = self._get_period(as_of)
        jt = self._get_journal_type()

        journal = Journal.objects.create(
            organization=self.org,
            journal_type=jt,
            period=period,
            journal_date=as_of,
            description=f"Asset acquisition - {asset.name}",
            currency_code=self.org.base_currency_code or "USD",
            exchange_rate=Decimal("1"),
            status="draft",
            created_by=self.user,
        )
        line_no = 1
        JournalLine.objects.create(
            journal=journal,
            line_number=line_no,
            account=asset.category.asset_account,
            description=f"Acquire {asset.name}",
            debit_amount=asset.acquisition_cost,
            created_by=self.user,
        )
        line_no += 1
        # If no separate clearing account is configured, use asset account as placeholder credit to balance.
        JournalLine.objects.create(
            journal=journal,
            line_number=line_no,
            account=asset.category.asset_account,
            description="Asset acquisition clearing",
            credit_amount=asset.acquisition_cost,
            created_by=self.user,
        )
        return self.posting_service.post(journal)

    @transaction.atomic
    def post_disposal(self, asset: FixedAsset, proceeds: Decimal, as_of: date):
        """Dispose an asset: remove cost/accumulated, record gain/loss."""
        self._ensure_accounts(asset.category)
        if asset.status == FixedAsset.Status.DISPOSED:
            raise FixedAssetPostingError(f"Asset {asset} already disposed.")

        period = self._get_period(as_of)
        jt = self._get_journal_type()
        journal = Journal.objects.create(
            organization=self.org,
            journal_type=jt,
            period=period,
            journal_date=as_of,
            description=f"Asset disposal - {asset.name}",
            currency_code=self.org.base_currency_code or "USD",
            exchange_rate=Decimal("1"),
            status="draft",
            created_by=self.user,
        )
        line_no = 1
        # Remove the asset cost
        JournalLine.objects.create(
            journal=journal,
            line_number=line_no,
            account=asset.category.asset_account,
            description=f"Dispose {asset.name}",
            credit_amount=asset.acquisition_cost,
            created_by=self.user,
        )
        line_no += 1
        # Remove accumulated depreciation (debit accumulated)
        JournalLine.objects.create(
            journal=journal,
            line_number=line_no,
            account=asset.category.accumulated_depreciation_account,
            description=f"Clear accumulated depreciation - {asset.name}",
            debit_amount=asset.salvage_value,  # minimal placeholder; actual accumulated not tracked here
            created_by=self.user,
        )
        line_no += 1

        # Record proceeds and gain/loss if configured
        gain = proceeds - asset.acquisition_cost + asset.salvage_value
        if gain >= 0 and asset.category.disposal_gain_account:
            JournalLine.objects.create(
                journal=journal,
                line_number=line_no,
                account=asset.category.disposal_gain_account,
                description=f"Gain on disposal - {asset.name}",
                credit_amount=gain,
                created_by=self.user,
            )
            line_no += 1
        elif gain < 0 and asset.category.disposal_loss_account:
            JournalLine.objects.create(
                journal=journal,
                line_number=line_no,
                account=asset.category.disposal_loss_account,
                description=f"Loss on disposal - {asset.name}",
                debit_amount=abs(gain),
                created_by=self.user,
            )
            line_no += 1

        posted = self.posting_service.post(journal)
        asset.status = FixedAsset.Status.DISPOSED
        asset.disposed_at = as_of
        asset.save(update_fields=["status", "disposed_at"])
        return posted

    def _depreciation_amount(self, asset: FixedAsset) -> Decimal:
        # Straight-line monthly depreciation
        depreciable = asset.acquisition_cost - asset.salvage_value
        months = max(asset.useful_life_months, 1)
        return (depreciable / Decimal(months)).quantize(Decimal("0.01"))

    def iter_depreciation(self, as_of: date) -> Iterable[DepreciationEntry]:
        for asset in FixedAsset.objects.filter(
            organization=self.org,
            status=FixedAsset.Status.ACTIVE,
            acquisition_date__lte=as_of,
        ):
            amount = self._depreciation_amount(asset)
            if amount > 0:
                yield DepreciationEntry(asset=asset, amount=amount)

    @transaction.atomic
    def post_depreciation(self, as_of: date):
        """Create and post a depreciation journal for all active assets."""
        period = self._get_period(as_of)
        jt = self._get_journal_type()
        entries = list(self.iter_depreciation(as_of))
        if not entries:
            return None

        journal = Journal.objects.create(
            organization=self.org,
            journal_type=jt,
            period=period,
            journal_date=as_of,
            description=f"Depreciation for {as_of:%B %Y}",
            currency_code=self.org.base_currency_code or "USD",
            exchange_rate=Decimal("1"),
            status="draft",
            created_by=self.user,
        )
        line_no = 1
        for entry in entries:
            self._ensure_accounts(entry.asset.category)
            JournalLine.objects.create(
                journal=journal,
                line_number=line_no,
                account=entry.asset.category.depreciation_expense_account,
                description=f"Depreciation - {entry.asset.name}",
                debit_amount=entry.amount,
                created_by=self.user,
            )
            line_no += 1
            JournalLine.objects.create(
                journal=journal,
                line_number=line_no,
                account=entry.asset.category.accumulated_depreciation_account,
                description=f"Accumulated depreciation - {entry.asset.name}",
                credit_amount=entry.amount,
                created_by=self.user,
            )
            line_no += 1

            AssetDepreciationSchedule.objects.update_or_create(
                organization=self.org,
                asset=entry.asset,
                period_start=date(as_of.year, as_of.month, 1),
                period_end=as_of,
                defaults={
                    "depreciation_amount": entry.amount,
                    "posted_journal": True,
                },
            )

        return self.posting_service.post(journal)
