from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict

from django.db.models import F, Sum
from django.db.models.functions import Coalesce

from accounting.models import Budget, GeneralLedger


@dataclass
class BudgetVarianceRow:
    account_id: int
    account_name: str
    budget_amount: Decimal
    actual_amount: Decimal
    variance: Decimal


class BudgetService:
    """Compares budgeted amounts against ledger actuals."""

    def __init__(self, budget: Budget):
        self.budget = budget

    def calculate_variances(self) -> list[BudgetVarianceRow]:
        rows: Dict[int, BudgetVarianceRow] = {}
        for line in self.budget.lines.select_related('account').all():
            budget_amount = line.total_amount
            actual = (
                GeneralLedger.objects.filter(
                    organization=self.budget.organization,
                    account=line.account,
                    period__fiscal_year=self.budget.fiscal_year,
                )
                .aggregate(
                    actual=Coalesce(
                        Sum(F('debit_amount') - F('credit_amount')),
                        Decimal('0'),
                    )
                )
            )
            actual_amount = actual['actual'] or Decimal('0')
            rows[line.account_id] = BudgetVarianceRow(
                account_id=line.account_id,
                account_name=line.account.account_name,
                budget_amount=budget_amount,
                actual_amount=actual_amount,
                variance=budget_amount - actual_amount,
            )
        return list(rows.values())
