from django.core.management.base import BaseCommand

from usermanagement.management.commands.setup_system_roles import (
    SPECIAL_PERMISSION_DEFINITIONS,
)
from usermanagement.models import Entity, Module, Permission


class Command(BaseCommand):
    help = 'Ensures granular journal and period permissions exist.'

    def handle(self, *args, **kwargs):
        for definition in SPECIAL_PERMISSION_DEFINITIONS:
            module = Module.objects.get_or_create(
                code=definition['module'],
                defaults={'name': definition['module'].title()},
            )[0]
            entity, _ = Entity.objects.get_or_create(
                module=module,
                code=definition['entity'],
                defaults={
                    'name': definition['entity'].replace('_', ' ').title(),
                    'description': f"{definition['entity'].replace('_', ' ').title()} management",
                    'is_active': True,
                },
            )
            permission, created = Permission.objects.get_or_create(
                module=module,
                entity=entity,
                action=definition['action'],
                defaults={
                    'name': definition['name'],
                    'description': definition['description'],
                    'is_active': True,
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created permission {permission.codename}"))
            else:
                self.stdout.write(self.style.WARNING(f"Permission {permission.codename} already exists"))
