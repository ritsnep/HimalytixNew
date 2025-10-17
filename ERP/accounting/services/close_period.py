from django.core.exceptions import ValidationError
from django.utils import timezone
from ..models import AccountingPeriod
import logging

logger = logging.getLogger(__name__)


def close_period(period: AccountingPeriod, user=None):
    """
    Close an accounting period.
    """
    if period.status != "open":
        logger.warning(
            "Attempted to close non-open period period_id=%s, status=%s",
            period.pk, period.status,
            extra={'period_id': period.pk, 'status': period.status}
        )
        raise ValidationError("Only open periods can be closed")
    period.status = "closed"
    period.closed_by = user if hasattr(period, "closed_by") else None
    period.closed_at = timezone.now() if hasattr(period, "closed_at") else None
    period.save()
    logger.info(
        "Closed period %s by user %s",
        period.pk, getattr(user, "pk", None),
        extra={'period_id': period.pk, 'user_id': getattr(user, "pk", None)}
    )
    return period
