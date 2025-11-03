from django.core.management.base import BaseCommand
from django.db import transaction

from accounting.models import VoucherModeConfig, default_ui_schema
from forms_designer.models import VoucherSchema, VoucherSchemaStatus
from forms_designer.utils import save_schema


class Command(BaseCommand):
    help = (
        "Create VoucherSchema entries for default vouchers that don't yet have a"
        " versioned schema, seeded from default_ui_schema."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Seed for all voucher configs, not only those marked is_default=1",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        only_defaults = not options.get("all", False)
        qs = VoucherModeConfig.objects.all()
        if only_defaults:
            qs = qs.filter(is_default=True)

        created = 0
        updated = 0
        
        for config in qs:
            existing = VoucherSchema.objects.filter(voucher_mode_config=config).order_by('-version')
            
            # Check if there's already an active published schema with data
            active_published = existing.filter(
                status=VoucherSchemaStatus.PUBLISHED,
                is_active=True
            ).first()
            
            if active_published:
                # Check if it has data
                has_data = (
                    (isinstance(active_published.schema.get('header'), dict) and active_published.schema['header']) or
                    (isinstance(active_published.schema.get('header'), list) and active_published.schema['header']) or
                    (isinstance(active_published.schema.get('lines'), dict) and active_published.schema['lines']) or
                    (isinstance(active_published.schema.get('lines'), list) and active_published.schema['lines'])
                )
                if has_data:
                    continue  # Skip, already has good data
            
            # Either no schemas exist, or existing ones are empty/draft
            # Create a new one from defaults
            schema = default_ui_schema()
            save_schema(config, schema, user=None)
            
            latest = (
                VoucherSchema.objects
                .filter(voucher_mode_config=config)
                .order_by('-version')
                .first()
            )
            if latest:
                latest.status = VoucherSchemaStatus.PUBLISHED
                latest.is_active = True
                latest.change_notes = (latest.change_notes or "").strip() or "Seeded default schema"
                latest.save(update_fields=["status", "is_active", "change_notes"])
                created += 1

        self.stdout.write(self.style.SUCCESS(f"Seeded {created} new schema(s), updated {updated} existing."))
