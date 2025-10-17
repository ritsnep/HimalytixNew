from django.core.management.base import BaseCommand
from usermanagement.models import Organization, Role, Permission

class Command(BaseCommand):
    help = 'Sets up system roles (Admin, Clerk, etc.) and assigns permissions for each organization.'

    def handle(self, *args, **kwargs):
        organizations = Organization.objects.all()
        for org in organizations:
            # Admin role: all permissions
            admin_role, _ = Role.objects.get_or_create(
                name='Admin',
                code='ADMIN',
                organization=org,
                is_system=True,
                defaults={'description': 'Full access to all features'}
            )
            all_permissions = Permission.objects.filter(is_active=True)
            admin_role.permissions.set(all_permissions)
            admin_role.save()

            # Clerk role: limited permissions
            clerk_role, _ = Role.objects.get_or_create(
                name='Clerk',
                code='CLERK',
                organization=org,
                is_system=True,
                defaults={'description': 'Clerk with limited access'}
            )
            clerk_permissions = Permission.objects.filter(
                action__in=['view', 'add', 'change'], is_active=True
            )
            clerk_role.permissions.set(clerk_permissions)
            clerk_role.save()

            # Add more roles as needed here (e.g., Manager, Auditor, etc.)
            # Example:
            # manager_role, _ = Role.objects.get_or_create(
            #     name='Manager',
            #     code='MANAGER',
            #     organization=org,
            #     is_system=True,
            #     defaults={'description': 'Manager with approval rights'}
            # )
            # manager_permissions = Permission.objects.filter(
            #     action__in=['view', 'add', 'change', 'approve'], is_active=True
            # )
            # manager_role.permissions.set(manager_permissions)
            # manager_role.save()

            self.stdout.write(self.style.SUCCESS(
                f"System roles (Admin, Clerk) and permissions set up for organization: {org.name}"
            )) 