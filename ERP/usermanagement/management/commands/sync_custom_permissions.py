from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission as AuthPermission
from django.contrib.contenttypes.models import ContentType
from usermanagement.models import Permission as CustomPermission, Entity
from accounting.models import Journal
from accounting.models import (
    AccountingPeriod, ChartOfAccount, CostCenter, Department,
    FiscalYear, JournalType, Project, TaxAuthority, TaxCode, TaxType, VoucherModeConfig
)

class Command(BaseCommand):
    help = 'Sync custom permissions from usermanagement.Permission to Django auth.Permission table.'

    def handle(self, *args, **options):
        # Map entity code to model class
        entity_model_map = {
            'journal': Journal,
            'accountingperiod': AccountingPeriod,
            'chartofaccount': ChartOfAccount,
            'costcenter': CostCenter,
            'department': Department,
            'fiscalyear': FiscalYear,
            'journaltype': JournalType,
            'project': Project,
            'taxauthority': TaxAuthority,
            'taxcode': TaxCode,
            'taxtype': TaxType,
            'vouchermodeconfig': VoucherModeConfig,
            # Add more as needed
        }
        created = 0
        for custom_perm in CustomPermission.objects.all():
            entity_code = custom_perm.entity.code
            model_class = entity_model_map.get(entity_code)
            if not model_class:
                self.stdout.write(self.style.WARNING(f'Skipping entity code: {entity_code} (no model mapping)'))
                continue
            content_type = ContentType.objects.get_for_model(model_class)
            auth_perm, was_created = AuthPermission.objects.get_or_create(
                codename=custom_perm.codename,
                content_type=content_type,
                defaults={
                    'name': custom_perm.name,
                }
            )
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f'Created auth.Permission: {auth_perm.codename}'))
        self.stdout.write(self.style.SUCCESS(f'Sync complete. {created} new permissions created.')) 