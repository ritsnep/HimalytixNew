from django.core.management.base import BaseCommand
from usermanagement.models import Module, Entity, Permission, Role

class Command(BaseCommand):
    help = 'Sets up initial permissions for the system'

    def handle(self, *args, **kwargs):
        # Create modules (ensure code is set for consistent codenames)
        accounting_module, _ = Module.objects.get_or_create(
            code='accounting',
            defaults={
                'name': 'Accounting',
                'description': 'Accounting module',
            }
        )

        pos_module, _ = Module.objects.get_or_create(
            code='pos',
            defaults={
                'name': 'Point of Sale',
                'description': 'Point of Sale module',
            }
        )

        # Create entities
        entities = [
            ('FiscalYear', 'Fiscal Year management'),
            ('AccountingPeriod', 'Accounting Period management'),
            ('ChartOfAccount', 'Chart of Accounts management'),
            ('DeliveryNote', 'Delivery Note / Challan management'),
            # Add other entities as needed...
        ]

        # POS entities
        pos_entities = [
            ('Sale', 'POS Sale transaction'),
            ('Cart', 'POS Shopping cart management'),
        ]

        # Process accounting entities
        for entity_name, description in entities:
            # Derive a machine-friendly code for the entity (lowercase, no spaces)
            entity_code = entity_name.replace(' ', '').lower()
            entity, _ = Entity.objects.get_or_create(
                module=accounting_module,
                code=entity_code,
                defaults={
                    'name': entity_name,
                    'description': description,
                }
            )

            # Create permissions for each entity
            actions = ['view', 'add', 'change', 'delete']
            for action in actions:
                codename = f'{accounting_module.code}_{entity.code}_{action}'
                Permission.objects.get_or_create(
                    codename=codename,
                    defaults={
                        'name': f'Can {action} {entity_name}',
                        'description': f'Can {action} {entity_name}',
                        'module': accounting_module,
                        'entity': entity,
                        'action': action,
                    }
                )

        # Process POS entities
        for entity_name, description in pos_entities:
            entity_code = entity_name.replace(' ', '').lower()
            entity, _ = Entity.objects.get_or_create(
                module=pos_module,
                code=entity_code,
                defaults={
                    'name': entity_name,
                    'description': description,
                }
            )

            # Create permissions for POS entities
            actions = ['view', 'add', 'change', 'delete']
            for action in actions:
                codename = f'{pos_module.code}_{entity.code}_{action}'
                Permission.objects.get_or_create(
                    codename=codename,
                    defaults={
                        'name': f'Can {action} {entity_name}',
                        'description': f'Can {action} {entity_name}',
                        'module': pos_module,
                        'entity': entity,
                        'action': action,
                    }
                )