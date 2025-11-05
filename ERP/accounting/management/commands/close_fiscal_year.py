from django.core.management.base import BaseCommand, CommandError

from accounting.models import FiscalYear
from accounting.services.fiscal_year_service import close_fiscal_year
from usermanagement.models import CustomUser


class Command(BaseCommand):
    help = "Closes a fiscal year and optionally auto-closes any remaining open periods."

    def add_arguments(self, parser):
        parser.add_argument(
            "fiscal_year",
            help="Fiscal year primary key or code (use --organization when passing a code).",
        )
        parser.add_argument(
            "--organization",
            type=int,
            help="Organization ID, required when referencing the fiscal year by code.",
        )
        parser.add_argument(
            "--user",
            type=int,
            help="User ID performing the close.",
        )
        parser.add_argument(
            "--auto-close-periods",
            action="store_true",
            help="Automatically close any open accounting periods before closing the fiscal year.",
        )

    def handle(self, *args, **options):
        fiscal_year_identifier = options["fiscal_year"]
        organization_id = options.get("organization")
        user_id = options.get("user")
        auto_close_periods = options.get("auto_close_periods", False)

        try:
            if organization_id:
                fiscal_year = FiscalYear.objects.get(code=fiscal_year_identifier, organization_id=organization_id)
            else:
                fiscal_year = FiscalYear.objects.get(pk=fiscal_year_identifier)
        except FiscalYear.DoesNotExist as exc:
            raise CommandError(f"Fiscal year '{fiscal_year_identifier}' was not found.") from exc

        if not user_id:
            raise CommandError("--user is required to close a fiscal year.")
        try:
            user = CustomUser.objects.get(pk=user_id)
        except CustomUser.DoesNotExist as exc:
            raise CommandError(f"User with ID {user_id} does not exist.") from exc

        fiscal_year = close_fiscal_year(
            fiscal_year,
            user=user,
            auto_close_open_periods=auto_close_periods,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Fiscal year {fiscal_year.code} for organization {fiscal_year.organization_id} closed successfully."
            )
        )
