"""
Management command to initialize voucher configuration data.
"""

from django.core.management.base import BaseCommand
from accounting.services.voucher_config import VoucherConfigManager


class Command(BaseCommand):
    help = 'Initialize default voucher types and fields'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset existing data before creating defaults',
        )

    def handle(self, *args, **options):
        self.stdout.write('Initializing voucher configuration...')

        if options['reset']:
            self.stdout.write('Resetting existing data...')
            from accounting.models import FieldConfig, ConfigurableField, VoucherType
            FieldConfig.objects.all().delete()
            ConfigurableField.objects.all().delete()
            VoucherType.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Existing data reset.'))

        # Create default voucher types
        self.stdout.write('Creating default voucher types...')
        VoucherConfigManager.create_default_voucher_types()
        self.stdout.write(self.style.SUCCESS('Voucher types created.'))

        # Create default fields for each voucher type
        from accounting.models import VoucherType
        voucher_types = VoucherType.objects.filter(is_active=True)
        for voucher_type in voucher_types:
            self.stdout.write(f'Creating default fields for {voucher_type.name}...')
            VoucherConfigManager.create_default_fields_for_voucher_type(voucher_type)
            self.stdout.write(self.style.SUCCESS(f'Fields created for {voucher_type.name}.'))

        self.stdout.write(self.style.SUCCESS('Voucher configuration initialization complete!'))