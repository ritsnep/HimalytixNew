from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Deprecated: UI schema normalization has been replaced by normalized voucher definitions."

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING(
            "normalize_voucher_schemas is deprecated. Use seed_voucher_definitions to rebuild configs."
        ))
