from django.core.management.base import BaseCommand
from usermanagement.models import Role, Permission, Organization

class Command(BaseCommand):
    help = 'Sets up the Accounting role and assigns journal-related permissions'

    def handle(self, *args, **kwargs):
        # Assuming a default organization exists. If not, this script will need adjustment.
        organization = Organization.objects.first()
        if not organization:
            self.stdout.write(self.style.ERROR('No organization found. Please create an organization first.'))
            return

        accounting_role, created = Role.objects.get_or_create(
            name='Accounting',
            code='accounting',
            organization=organization,
            defaults={'description': 'Role for accounting staff with permissions to manage journal entries.'}
        )

        if created:
            self.stdout.write(self.style.SUCCESS('Successfully created "Accounting" role.'))
        else:
            self.stdout.write(self.style.WARNING('"Accounting" role already exists.'))

        permissions_to_assign = [
            'submit_journal',
            'modify_journal',
        ]

        for perm_codename in permissions_to_assign:
            try:
                permission = Permission.objects.get(codename=perm_codename)
                accounting_role.permissions.add(permission)
                self.stdout.write(self.style.SUCCESS(f'Assigned permission "{perm_codename}" to "Accounting" role.'))
            except Permission.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Permission "{perm_codename}" not found.'))
