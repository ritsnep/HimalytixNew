from django.core.management.base import BaseCommand
from django.utils import timezone

from accounting.models import IntegrationEvent
from enterprise.models import IntegrationEndpoint


class Command(BaseCommand):
    help = "Stub bank feed sync: records a sync event for active bank feed endpoints."

    def handle(self, *args, **options):
        endpoints = IntegrationEndpoint.objects.filter(
            connector_type=IntegrationEndpoint.ConnectorType.BANK_FEED,
            is_active=True,
        )
        if not endpoints:
            self.stdout.write(self.style.WARNING("No active bank feed endpoints found."))
            return

        for ep in endpoints:
            IntegrationEvent.objects.create(
                event_type="bank_feed.sync",
                payload={
                    "endpoint": ep.name,
                    "synced_at": timezone.now().isoformat(),
                    "organization_id": ep.organization_id,
                },
                source_object="IntegrationEndpoint",
                source_id=str(ep.pk),
            )
            self.stdout.write(self.style.SUCCESS(f"Recorded bank feed sync for {ep.name}"))
