"""Management command to set or clear tenant-specific favicon URLs."""
from __future__ import annotations

import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from tenancy.models import Tenant, TenantConfig

BRANDING_FAVICON_KEY = "branding.favicon_url"


class Command(BaseCommand):
    help = "Set or clear the tenant-specific favicon URL used by the branding context."

    def add_arguments(self, parser):
        parser.add_argument(
            "tenant",
            help="Tenant code, slug, or UUID to update.",
        )
        parser.add_argument(
            "--url",
            dest="favicon_url",
            help="Absolute URL or /static/ path to the favicon icon.",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Remove the custom favicon so the default icon is used.",
        )

    def handle(self, *args, **options):
        identifier = options["tenant"]
        favicon_url = (options.get("favicon_url") or "").strip()
        clear_flag = options["clear"]

        if clear_flag and favicon_url:
            raise CommandError("Use --clear or --url, but not both.")
        if not clear_flag and not favicon_url:
            raise CommandError("Provide --url with a value, or pass --clear to remove the favicon.")

        tenant = self._get_tenant(identifier)
        if tenant is None:
            raise CommandError(f"No tenant found matching '{identifier}'.")

        if clear_flag:
            deleted, _ = TenantConfig.objects.filter(
                tenant=tenant,
                config_key=BRANDING_FAVICON_KEY,
            ).delete()
            if deleted:
                self.stdout.write(self.style.SUCCESS(f"Cleared favicon for tenant {tenant.code}."))
            else:
                self.stdout.write("No custom favicon was previously configured; nothing to clear.")
            return

        TenantConfig.objects.update_or_create(
            tenant=tenant,
            config_key=BRANDING_FAVICON_KEY,
            defaults={
                "config_value": favicon_url,
                "data_type": "string",
            },
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Set favicon for tenant {tenant.code} to '{favicon_url}'."
            )
        )

    def _get_tenant(self, identifier: str) -> Tenant | None:
        filters = Q(code__iexact=identifier) | Q(slug__iexact=identifier)
        try:
            uuid.UUID(str(identifier))
        except (ValueError, TypeError):
            pass
        else:
            filters |= Q(tenant_uuid__iexact=identifier)
        return Tenant.objects.filter(filters).first()
