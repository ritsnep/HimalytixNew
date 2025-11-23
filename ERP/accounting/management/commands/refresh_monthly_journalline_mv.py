import logging

from django.core.management.base import BaseCommand
from django.db import connection

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Refresh the accounting_monthly_journalline_mv materialized view."

    def handle(self, *args, **options):
        refresh_sql = "REFRESH MATERIALIZED VIEW CONCURRENTLY accounting_monthly_journalline_mv;"
        fallback_sql = "REFRESH MATERIALIZED VIEW accounting_monthly_journalline_mv;"

        with connection.cursor() as cursor:
            try:
                cursor.execute(refresh_sql)
                self.stdout.write(self.style.SUCCESS("Refreshed materialized view concurrently."))
            except Exception as exc:
                logger.warning(
                    "Concurrent refresh failed for accounting_monthly_journalline_mv: %s. Fallback to blocking refresh.",
                    exc,
                )
                cursor.execute(fallback_sql)
                self.stdout.write(self.style.WARNING("Refreshed materialized view with blocking fallback."))
