from django.core.management.base import BaseCommand
from usermanagement.models import Module, Entity, Permission, Role

class Command(BaseCommand):
    help = 'Sets up initial permissions for the system'

    def handle(self, *args, **kwargs):
        # Create modules
        accounting_module, _ = Module.objects.get_or_create(
            name='Accounting',
            description='Accounting module'
        )

        # Create entities
        entities = [
            ('FiscalYear', 'Fiscal Year management'),
            ('AccountingPeriod', 'Accounting Period management'),
            ('ChartOfAccount', 'Chart of Accounts management'),
            # Add other entities...
        ]

        for entity_name, description in entities:
            entity, _ = Entity.objects.get_or_create(
                module=accounting_module,
                name=entity_name,
                description=description
            )

            # Create permissions for each entity
            actions = ['view', 'add', 'change', 'delete']
            for action in actions:
                Permission.objects.get_or_create(
                    name=f'Can {action} {entity_name}',
                    codename=f'accounting_{entity_name.lower()}_{action}',
                    description=f'Can {action} {entity_name}',
                    module=accounting_module,
                    entity=entity,
                    action=action
                ) 