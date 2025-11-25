from django.core.management.base import BaseCommand

from usermanagement.models import Organization
from usermanagement.signals import _seed_noc_vendor


class Command(BaseCommand):
    help = "Reseed Nepal Oil Corporation vendor and AP defaults for all companies."

    def handle(self, *args, **options):
        created = 0
        for org in Organization.objects.all():
            before = org.vendors.filter(code="NOC").exists()
            _seed_noc_vendor(org)
            after = org.vendors.filter(code="NOC").exists()
            if not before and after:
                created += 1
        self.stdout.write(self.style.SUCCESS(f"NOC vendor seeded for {created} companies."))
