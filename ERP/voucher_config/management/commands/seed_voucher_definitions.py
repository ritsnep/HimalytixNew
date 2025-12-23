from __future__ import annotations

from typing import Iterable

from django.core.management.base import BaseCommand, CommandError

from usermanagement.models import Organization
from voucher_config.seeding import seed_voucher_config_master


class Command(BaseCommand):
    help = "Seed VoucherConfigMaster and related voucher config tables."

    def add_arguments(self, parser):
        parser.add_argument(
            "--org",
            default="all",
            help="Organization id or 'all' (default).",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing voucher config master data before seeding.",
        )
        parser.add_argument(
            "--repair",
            action="store_true",
            help="Repair missing fields on existing configs (default).",
        )

    def handle(self, *args, **options):
        org_arg = options["org"]
        reset = bool(options["reset"])
        repair = bool(options["repair"] or not options["reset"])

        if org_arg == "all":
            orgs: Iterable[Organization] = Organization.objects.all()
        else:
            try:
                org_id = int(org_arg)
            except (TypeError, ValueError) as exc:
                raise CommandError("--org must be 'all' or a numeric id.") from exc
            orgs = Organization.objects.filter(id=org_id)
            if not orgs.exists():
                raise CommandError(f"Organization {org_id} not found.")

        for org in orgs:
            stats = seed_voucher_config_master(org, reset=reset, repair=repair)
            self.stdout.write(
                self.style.SUCCESS(
                    f"{org.code}: created={stats['created']} repaired={stats['repaired']}"
                )
            )
