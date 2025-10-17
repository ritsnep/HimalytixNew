from decimal import Decimal
from django.db.models import Sum
from ..models import ChartOfAccount, GeneralLedger, FiscalYear, Organization
import logging

logger = logging.getLogger(__name__)


def get_trial_balance(organization: Organization, fiscal_year: FiscalYear):
    """Return trial balance data for an organization and fiscal year.

    This aggregates all general ledger entries for the supplied fiscal year and
    returns a list of accounts with their total debits, credits and resulting
    balance.  All accounts for the organisation are included even if there is no
    activity during the year."""

    accounts = (
        ChartOfAccount.objects.filter(organization=organization, is_active=True)
        .values("id", "account_code", "account_name")
        .order_by("account_code")
    )

    gl_totals = (
        GeneralLedger.objects.filter(
            organization=organization,
            period__fiscal_year=fiscal_year,
            is_archived=False,
        )
        .values("account_id")
        .annotate(
            debit_total=Sum("debit_amount"),
            credit_total=Sum("credit_amount"),
        )
    )
    totals_map = {
        row["account_id"]: row for row in gl_totals
    }

    results = []
    for account in accounts:
        totals = totals_map.get(account["id"], {})
        debit = totals.get("debit_total") or Decimal("0")
        credit = totals.get("credit_total") or Decimal("0")
        balance = debit - credit
        results.append(
            {
                "account_id": account["id"],
                "account_code": account["account_code"],
                "account_name": account["account_name"],
                "debit_total": debit,
                "credit_total": credit,
                "balance": balance,
            }
        )
    logger.info(
        "Trial balance generated for organization %s, fiscal year %s",
        organization.pk, fiscal_year.pk,
        extra={'organization_id': organization.pk, 'fiscal_year_id': fiscal_year.pk}
    )
    return results