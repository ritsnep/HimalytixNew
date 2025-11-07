from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from accounting.models import (
    AccountingPeriod,
    AccountingSettings,
    ChartOfAccount,
    FiscalYear,
    GeneralLedger,
    Journal,
    JournalLine,
    JournalType,
)
from accounting.services.posting_service import PostingService
from accounting.utils.audit import log_audit_event

FOUR_PLACES = Decimal("0.0000")


@dataclass
class YearEndClosingResult:
    closing_journal: Optional[Journal]
    opening_journal: Optional[Journal]
    net_result: Decimal


class YearEndClosingError(ValidationError):
    """Raised when the year-end closing process cannot proceed."""


class YearEndClosingService:
    """Generates year-end closing and opening balance journals."""

    def __init__(self, fiscal_year: FiscalYear, user):
        self.fiscal_year = fiscal_year
        self.user = user
        self.organization = fiscal_year.organization
        self.settings: Optional[AccountingSettings] = getattr(
            self.organization, "accounting_settings", None
        )
        if self.settings is None:
            raise YearEndClosingError(
                "Accounting settings must specify retained earnings before closing the fiscal year."
            )
        self._posting_service = PostingService(user)

    def close(self) -> YearEndClosingResult:
        with transaction.atomic():
            closing_journal, net_result = self._ensure_closing_journal()
            opening_journal = None
            if self.settings.auto_rollover_closing and net_result is not None:
                opening_journal = self._ensure_opening_balances()
            return YearEndClosingResult(
                closing_journal=closing_journal,
                opening_journal=opening_journal,
                net_result=net_result or Decimal("0"),
            )

    # ------------------------------------------------------------------
    # Closing journal
    # ------------------------------------------------------------------
    def _ensure_closing_journal(self) -> tuple[Optional[Journal], Optional[Decimal]]:
        existing = (
            Journal.objects.filter(
                organization=self.organization,
                metadata__closing_type="year_end",
                metadata__fiscal_year_id=str(self.fiscal_year.pk),
            )
            .order_by("-journal_date")
            .first()
        )
        if existing:
            net_result = Decimal(existing.metadata.get("net_result", "0"))
            return existing, net_result

        balances = self._pnl_balances()
        if not balances:
            # Nothing to close, but return zero result
            return None, Decimal("0")

        period = self._resolve_period_for_closing()
        journal_type = self._resolve_closing_journal_type()

        journal_metadata = {
            "closing_type": "year_end",
            "fiscal_year_id": str(self.fiscal_year.pk),
            "generated_at": timezone.now().isoformat(),
            "is_closing_entry": True,
        }

        journal = Journal.objects.create(
            organization=self.organization,
            journal_type=journal_type,
            period=period,
            journal_date=self.fiscal_year.end_date,
            description=f"Year-end closing entry for {self.fiscal_year.code}",
            currency_code=self.organization.base_currency_code or "USD",
            exchange_rate=Decimal("1"),
            status="draft",
            created_by=self.user,
            metadata=journal_metadata,
            is_locked=False,
        )

        line_number = 1
        total_debits = Decimal("0")
        total_credits = Decimal("0")
        for balance in balances:
            account = balance.account
            amount = balance.amount
            if amount == 0:
                continue
            description = f"Close {account.account_name}"
            debit = credit = Decimal("0")
            if balance.net > 0:
                credit = amount
                total_credits += amount
            else:
                debit = amount
                total_debits += amount

            JournalLine.objects.create(
                journal=journal,
                line_number=line_number,
                account=account,
                description=description,
                debit_amount=debit,
                credit_amount=credit,
                amount_txn=amount,
                amount_base=amount,
                fx_rate=Decimal("1"),
                created_by=self.user,
            )
            line_number += 1

        net_result = (total_debits - total_credits).quantize(FOUR_PLACES)
        if net_result != 0:
            retained = self.settings.retained_earnings_account
            retained_description = "Transfer net result to retained earnings"
            if net_result > 0:
                credit = net_result
                debit = Decimal("0")
            else:
                debit = net_result.copy_abs().quantize(FOUR_PLACES)
                credit = Decimal("0")
            JournalLine.objects.create(
                journal=journal,
                line_number=line_number,
                account=retained,
                description=retained_description,
                debit_amount=debit,
                credit_amount=credit,
                amount_txn=net_result.copy_abs().quantize(FOUR_PLACES),
                amount_base=net_result.copy_abs().quantize(FOUR_PLACES),
                fx_rate=Decimal("1"),
                created_by=self.user,
            )
            if net_result > 0:
                total_credits += net_result
            else:
                total_debits += net_result.copy_abs().quantize(FOUR_PLACES)
            line_number += 1

        journal.metadata.update(
            {
                "net_result": str(net_result),
                "result_nature": "profit" if net_result > 0 else "loss" if net_result < 0 else "break_even",
                "retained_earnings_account_id": self.settings.retained_earnings_account.pk,
                "period_id": period.pk,
            }
        )
        journal.save(update_fields=["metadata", "exchange_rate"])

        posted = self._posting_service.post(journal)
        log_audit_event(
            self.user,
            posted,
            "year_end_closed",
            details=f"Year-end closing journal {posted.journal_number} posted for fiscal year {self.fiscal_year.code}.",
        )
        return posted, net_result

    def _resolve_period_for_closing(self) -> AccountingPeriod:
        period = (
            self.fiscal_year.periods.filter(start_date__lte=self.fiscal_year.end_date)
            .order_by("-period_number")
            .first()
        )
        if period is None:
            raise YearEndClosingError("Fiscal year has no accounting periods configured.")
        if period.status != "open":
            period.status = "open"
            period.save(update_fields=["status"])
        return period

    def _resolve_closing_journal_type(self) -> JournalType:
        defaults = {
            "name": "Year-End Closing",
            "description": "System generated year-end closing entry",
            "auto_numbering_prefix": "YE",
            "fiscal_year_prefix": True,
            "is_system_type": True,
        }
        journal_type, _ = JournalType.objects.get_or_create(
            organization=self.organization,
            code="YECL",
            defaults=defaults,
        )
        return journal_type

    # ------------------------------------------------------------------
    # Opening balances
    # ------------------------------------------------------------------
    def _ensure_opening_balances(self) -> Optional[Journal]:
        next_year = (
            FiscalYear.objects.filter(
                organization=self.organization,
                start_date__gt=self.fiscal_year.end_date,
            )
            .order_by("start_date")
            .first()
        )
        if not next_year:
            return None

        existing = (
            Journal.objects.filter(
                organization=self.organization,
                metadata__closing_type="year_opening",
                metadata__source_fiscal_year=str(self.fiscal_year.pk),
            )
            .order_by("journal_date")
            .first()
        )
        if existing:
            return existing

        period = next_year.periods.order_by("period_number").first()
        if not period:
            return None

        balances = self._balance_sheet_balances()
        if not balances:
            return None

        journal_type = self._resolve_closing_journal_type()
        journal = Journal.objects.create(
            organization=self.organization,
            journal_type=journal_type,
            period=period,
            journal_date=next_year.start_date,
            description=f"Opening balances from {self.fiscal_year.code}",
            currency_code=self.organization.base_currency_code or "USD",
            exchange_rate=Decimal("1"),
            status="draft",
            created_by=self.user,
            metadata={
                "closing_type": "year_opening",
                "source_fiscal_year": str(self.fiscal_year.pk),
                "generated_at": timezone.now().isoformat(),
            },
        )

        line_number = 1
        total_debits = Decimal("0")
        total_credits = Decimal("0")
        for balance in balances:
            account = balance.account
            amount = balance.amount
            if amount == 0:
                continue
            if balance.net >= 0:
                debit = amount
                credit = Decimal("0")
                total_debits += amount
            else:
                debit = Decimal("0")
                credit = amount
                total_credits += amount

            JournalLine.objects.create(
                journal=journal,
                line_number=line_number,
                account=account,
                description=f"Opening balance for {account.account_name}",
                debit_amount=debit,
                credit_amount=credit,
                amount_txn=balance.net.copy_abs().quantize(FOUR_PLACES),
                amount_base=balance.net.copy_abs().quantize(FOUR_PLACES),
                fx_rate=Decimal("1"),
                created_by=self.user,
            )
            line_number += 1

        difference = (total_debits - total_credits).quantize(FOUR_PLACES)
        if difference != 0:
            adjustment_account = self.settings.current_year_income_account
            if adjustment_account is None:
                raise YearEndClosingError(
                    "Current year income account must be configured to balance opening entry."
                )
            if difference > 0:
                credit = difference
                debit = Decimal("0")
            else:
                debit = difference.copy_abs().quantize(FOUR_PLACES)
                credit = Decimal("0")
            JournalLine.objects.create(
                journal=journal,
                line_number=line_number,
                account=adjustment_account,
                description="Opening balance rounding adjustment",
                debit_amount=debit,
                credit_amount=credit,
                amount_txn=difference.copy_abs().quantize(FOUR_PLACES),
                amount_base=difference.copy_abs().quantize(FOUR_PLACES),
                fx_rate=Decimal("1"),
                created_by=self.user,
            )

        posted = self._posting_service.post(journal)
        log_audit_event(
            self.user,
            posted,
            "year_opening_posted",
            details=f"Opening journal {posted.journal_number} posted for fiscal year {next_year.code}.",
        )
        return posted

    # ------------------------------------------------------------------
    # Aggregation helpers
    # ------------------------------------------------------------------
    class _Balance:
        __slots__ = ("account", "net", "amount")

        def __init__(self, account: ChartOfAccount, net: Decimal):
            self.account = account
            self.net = net
            self.amount = abs(net).quantize(FOUR_PLACES)

    def _pnl_balances(self) -> list[_Balance]:
        queryset = (
            GeneralLedger.objects.filter(
                organization_id=self.organization,
                transaction_date__gte=self.fiscal_year.start_date,
                transaction_date__lte=self.fiscal_year.end_date,
                account__account_type__nature__in=["income", "expense"],
                is_closing_entry=False,
            )
            .values("account_id")
            .annotate(
                debit=Sum("functional_debit_amount"),
                credit=Sum("functional_credit_amount"),
            )
        )

        account_map = ChartOfAccount.objects.in_bulk([row["account_id"] for row in queryset])
        balances: list[YearEndClosingService._Balance] = []
        for row in queryset:
            account = account_map.get(row["account_id"])
            if not account:
                continue
            debit = Decimal(row.get("debit") or 0)
            credit = Decimal(row.get("credit") or 0)
            net = (debit - credit).quantize(FOUR_PLACES)
            if net == 0:
                continue
            balances.append(self._Balance(account, net))
        balances.sort(key=lambda bal: bal.account.account_code)
        return balances

    def _balance_sheet_balances(self) -> list[_Balance]:
        queryset = (
            GeneralLedger.objects.filter(
                organization_id=self.organization,
                transaction_date__lte=self.fiscal_year.end_date,
                account__account_type__nature__in=["asset", "liability", "equity"],
            )
            .values("account_id")
            .annotate(
                debit=Sum("functional_debit_amount"),
                credit=Sum("functional_credit_amount"),
            )
        )
        account_map = ChartOfAccount.objects.in_bulk([row["account_id"] for row in queryset])
        balances: list[YearEndClosingService._Balance] = []
        for row in queryset:
            account = account_map.get(row["account_id"])
            if not account:
                continue
            debit = Decimal(row.get("debit") or 0)
            credit = Decimal(row.get("credit") or 0)
            net = (debit - credit).quantize(FOUR_PLACES)
            if net == 0:
                continue
            balances.append(self._Balance(account, net))
        balances.sort(key=lambda bal: bal.account.account_code)
        return balances
