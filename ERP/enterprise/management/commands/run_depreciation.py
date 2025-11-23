from datetime import date

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from enterprise.services import FixedAssetService
from usermanagement.models import Organization

User = get_user_model()


class Command(BaseCommand):
    help = "Run monthly depreciation for all active assets in an organization."

    def add_arguments(self, parser):
        parser.add_argument("--org-code", required=True, help="Organization code")
        parser.add_argument(
            "--as-of",
            type=str,
            help="Date (YYYY-MM-DD). Defaults to last day of current month.",
        )
        parser.add_argument(
            "--user",
            required=True,
            help="Username to attribute the journal posting.",
        )

    def handle(self, *args, **options):
        org_code = options["org_code"]
        as_of_str = options.get("as_of")
        username = options["user"]

        try:
            org = Organization.objects.get(code=org_code)
        except Organization.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Organization {org_code} not found"))
            return

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"User {username} not found"))
            return

        as_of = date.fromisoformat(as_of_str) if as_of_str else date.today().replace(day=1)
        service = FixedAssetService(user=user, org=org)
        journal = service.post_depreciation(as_of)
        if journal:
            self.stdout.write(self.style.SUCCESS(f"Posted depreciation journal {journal.journal_id}"))
        else:
            self.stdout.write(self.style.WARNING("No assets to depreciate"))
