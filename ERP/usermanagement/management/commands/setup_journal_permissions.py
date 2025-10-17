from django.core.management.base import BaseCommand
from usermanagement.models import Module, Entity, Permission

class Command(BaseCommand):
    help = 'Sets up initial permissions for journal entries'

    def handle(self, *args, **kwargs):
        accounting_module, _ = Module.objects.get_or_create(
            name='Accounting',
            code='accounting',
            description='Accounting module'
        )

        journal_entity, _ = Entity.objects.get_or_create(
            module=accounting_module,
            name='Journal',
            code='journal',
            description='Journal Entry management'
        )

        permissions_to_create = [
            ('submit_journal', 'Can submit journal entry'),
            ('modify_journal', 'Can modify journal entry'),
        ]

        for codename, name in permissions_to_create:
            permission, created = Permission.objects.get_or_create(
                name=name,
                codename=codename,
                defaults={
                    'description': name,
                    'module': accounting_module,
                    'entity': journal_entity,
                    'action': codename.split('_')[0]
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Successfully created permission: {codename}'))
            else:
                self.stdout.write(self.style.WARNING(f'Permission already exists: {codename}'))