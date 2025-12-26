import logging

from django.db import connection

from inventory.models import VendorPriceHistory, CustomerPriceHistory

logger = logging.getLogger(__name__)


def _safe_create(model, **kwargs):
    """
    Create a record only if the backing table exists; otherwise skip gracefully.

    This prevents posting from crashing when price history tables haven't been migrated.
    """
    try:
        existing = connection.introspection.table_names()
        if model._meta.db_table not in existing:
            logger.warning("Price history table missing (%s); skipping create.", model._meta.db_table)
            return None
        return model.objects.create(**kwargs)
    except Exception as exc:
        logger.warning("Price history create skipped for %s: %s", model.__name__, exc)
        return None


class PriceHistoryService:
    """Record vendor/customer price history snapshots."""

    @staticmethod
    def record_vendor_price_history(
        vendor,
        product,
        unit_price,
        doc_date,
        organization,
        created_by=None,
        currency=None,
        quantity=None,
        doc_ref=None,
    ):
        return _safe_create(
            VendorPriceHistory,
            organization=organization,
            vendor=vendor,
            product=product,
            purchase_rate=unit_price,
            doc_date=doc_date,
            created_by=created_by,
            currency=currency,
            quantity=quantity,
            doc_ref=doc_ref,
        )

    @staticmethod
    def record_customer_price_history(
        customer,
        product,
        unit_price,
        doc_date,
        organization,
        created_by=None,
        currency=None,
        quantity=None,
        doc_ref=None,
    ):
        return _safe_create(
            CustomerPriceHistory,
            organization=organization,
            customer=customer,
            product=product,
            sales_rate=unit_price,
            doc_date=doc_date,
            created_by=created_by,
            currency=currency,
            quantity=quantity,
            doc_ref=doc_ref,
        )
