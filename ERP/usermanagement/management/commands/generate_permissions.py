from django.core.management.base import BaseCommand
from django.apps import apps
from usermanagement.models import Module, Entity, Permission

class Command(BaseCommand):
    help = 'Generates permissions for all models in the system'

    def handle(self, *args, **kwargs):
        # Get all installed apps
        for app_config in apps.get_app_configs():
            if app_config.name.startswith('ERP.'):
                module_name = app_config.label
                module, _ = Module.objects.get_or_create(
                    name=module_name.title(),
                    code=module_name.lower(),
                    description=f'Module for {module_name}'
                )

                # Get all models in the app
                for model in app_config.get_models():
                    if model._meta.abstract:
                        continue

                    entity_name = model._meta.model_name
                    # Special case: Journal model as Voucher Entry
                    if entity_name == 'journal':
                        entity_code = 'voucher_entry'
                        entity_display_name = 'Voucher Entry'
                    else:
                        entity_code = entity_name
                        entity_display_name = entity_name.title()

                    entity, _ = Entity.objects.get_or_create(
                        module=module,
                        code=entity_code,
                        defaults={
                            'name': entity_display_name,
                            'description': f'Entity for {entity_display_name}'
                        }
                    )

                    # Create CRUD permissions
                    actions = ['view', 'add', 'change', 'delete']
                    for action in actions:
                        Permission.objects.get_or_create(
                            name=f'Can {action} {entity_display_name}',
                            codename=f'{module_name}_{entity_code}_{action}',
                            description=f'Can {action} {entity_display_name}',
                            module=module,
                            entity=entity,
                            action=action
                        )

        self.stdout.write(self.style.SUCCESS('Successfully generated permissions')) 