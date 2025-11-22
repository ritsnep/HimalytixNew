from django.core.management.base import BaseCommand

from billing.services import resync_failed_invoices


class Command(BaseCommand):
    help = "Resend unsynced invoices to CBMS."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None, help="Limit number of invoices to resync.")

    def handle(self, *args, **options):
        limit = options.get("limit")
        count = resync_failed_invoices(limit=limit)
        self.stdout.write(self.style.SUCCESS(f"Resynced {count} invoices."))
