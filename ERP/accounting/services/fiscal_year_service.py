from __future__ import annotations

import logging
from typing import Optional

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from accounting.models import AccountingPeriod, FiscalYear
from accounting.services.close_period import close_period
from accounting.services.year_end_closing import YearEndClosingError, YearEndClosingService
from accounting.utils.audit import log_audit_event
from usermanagement.models import CustomUser
from usermanagement.utils import PermissionUtils

logger = logging.getLogger(__name__)


def _check_permission(user: Optional[CustomUser], fiscal_year: FiscalYear, action: str) -> None:
    if user is None:
        raise PermissionDenied("A user with appropriate permissions is required for this action.")
    if PermissionUtils.has_permission(user, fiscal_year.organization, "accounting", "fiscalyear", action):
        return
    raise PermissionDenied("You do not have permission to perform this action.")


@transaction.atomic
def close_fiscal_year(
    fiscal_year: FiscalYear,
    user: Optional[CustomUser] = None,
    *,
    auto_close_open_periods: bool = False,
) -> FiscalYear:
    """
    Closes all periods belonging to the fiscal year (optionally auto-closing any that remain open)
    and marks the fiscal year as closed.
    """
    fiscal_year = FiscalYear.objects.select_for_update().get(pk=fiscal_year.pk)
    _check_permission(user, fiscal_year, "close_fiscalyear")

    open_periods = fiscal_year.periods.filter(status="open").order_by("period_number")
    if open_periods.exists() and not auto_close_open_periods:
        raise ValidationError("All accounting periods must be closed before closing the fiscal year.")

    closing_result = None
    try:
        closing_service = YearEndClosingService(fiscal_year, user)
        closing_result = closing_service.close()
    except YearEndClosingError as exc:
        raise ValidationError(exc.messages) from exc

    open_periods = fiscal_year.periods.filter(status="open").order_by("period_number")
    if open_periods.exists():
        for period in open_periods:
            close_period(period, user=user)

    if fiscal_year.status == "closed":
        logger.info("Fiscal year %s is already closed.", fiscal_year.code)
        return fiscal_year

    fiscal_year.status = "closed"
    fiscal_year.closed_at = timezone.now()
    if hasattr(fiscal_year, "closed_by"):
        fiscal_year.closed_by = user
    fiscal_year.is_current = False
    fiscal_year.save(update_fields=["status", "closed_at", "closed_by", "is_current", "updated_at"])

    audit_details = f"Fiscal year {fiscal_year.code} closed."
    if closing_result and closing_result.net_result is not None:
        audit_details += f" Net result transferred: {closing_result.net_result}."
    log_audit_event(user, fiscal_year, "close_fiscal_year", details=audit_details)
    logger.info("Fiscal year %s closed by %s", fiscal_year.code, getattr(user, "pk", None))

    # Promote the next fiscal year (if available) to current.
    next_year = (
        FiscalYear.objects.filter(
            organization=fiscal_year.organization,
            start_date__gt=fiscal_year.end_date,
        )
        .order_by("start_date")
        .first()
    )
    if next_year and next_year.status != "closed" and not next_year.is_current:
        next_year.is_current = True
        next_year.save(update_fields=["is_current", "updated_at"])
        log_audit_event(user, next_year, "promoted_to_current", details="Promoted to current fiscal year.")

    return fiscal_year


@transaction.atomic
def reopen_fiscal_year(fiscal_year: FiscalYear, user: Optional[CustomUser] = None) -> FiscalYear:
    """
    Reopens a closed fiscal year. The caller is responsible for re-opening individual periods as needed.
    """
    fiscal_year = FiscalYear.objects.select_for_update().get(pk=fiscal_year.pk)
    _check_permission(user, fiscal_year, "reopen_fiscalyear")

    if fiscal_year.status != "closed":
        raise ValidationError("Only closed fiscal years can be reopened.")

    fiscal_year.status = "open"
    fiscal_year.closed_at = None
    if hasattr(fiscal_year, "closed_by"):
        fiscal_year.closed_by = None
    fiscal_year.is_current = True
    fiscal_year.updated_at = timezone.now()
    fiscal_year.save(update_fields=["status", "closed_at", "closed_by", "is_current", "updated_at"])

    log_audit_event(user, fiscal_year, "reopen_fiscal_year", details=f"Fiscal year {fiscal_year.code} reopened.")
    logger.info("Fiscal year %s reopened by %s", fiscal_year.code, getattr(user, "pk", None))
    return fiscal_year
