from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from accounting.models import BankStatement, BankTransaction


class BankReconciliationService:
    """Matches statement lines against recorded bank transactions."""

    DATE_TOLERANCE = timedelta(days=2)
    AMOUNT_TOLERANCE = Decimal("0.01")

    def __init__(self, statement: BankStatement):
        self.statement = statement

    def match(self) -> int:
        matched = 0
        for line in self.statement.lines.select_related("matched_transaction").all():
            if line.matched_transaction_id:
                continue
            candidate = (
                BankTransaction.objects.filter(
                    bank_account=self.statement.bank_account,
                    amount=line.amount,
                )
                .filter(
                    transaction_date__lte=line.line_date + self.DATE_TOLERANCE,
                    transaction_date__gte=line.line_date - self.DATE_TOLERANCE,
                    is_reconciled=False,
                )
                .first()
            )
            if candidate:
                line.matched_transaction = candidate
                line.save(update_fields=["matched_transaction"])
                candidate.is_reconciled = True
                candidate.reconciled_at = line.line_date
                candidate.save(update_fields=["is_reconciled", "reconciled_at"])
                matched += 1
        if matched:
            self.statement.status = "matched"
            self.statement.save(update_fields=["status"])
        return matched
