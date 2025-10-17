from django.core.management.base import BaseCommand
from usermanagement.models import Organization, Role, Permission, UserRole, CustomUser

class Command(BaseCommand):
    help = 'Sets up default roles and permissions for organizations'

    def handle(self, *args, **kwargs):
        # Get all organizations
        organizations = Organization.objects.all()
        
        for org in organizations:
            # Create Admin role
            admin_role, _ = Role.objects.get_or_create(
                name='Administrator',
                organization=org,
                description='Full access to all features',
                is_system=True
            )
            
            # Get all permissions
            all_permissions = Permission.objects.all()
            admin_role.permissions.set(all_permissions)
            
            # Create User role with limited permissions
            user_role, _ = Role.objects.get_or_create(
                name='User',
                organization=org,
                description='Basic user access',
                is_system=True
            )
            
            # Assign view permissions to user role
            view_permissions = Permission.objects.filter(action='view')
            user_role.permissions.set(view_permissions)
            
            # Assign roles to users
            for user in CustomUser.objects.filter(organization=org):
                if user.role == 'admin':
                    UserRole.objects.get_or_create(
                        user=user,
                        role=admin_role,
                        organization=org,
                        is_active=True
                    )
                else:
                    UserRole.objects.get_or_create(
                        user=user,
                        role=user_role,
                        organization=org,
                        is_active=True
                    )

        self.stdout.write(self.style.SUCCESS('Successfully set up default roles and permissions')) 