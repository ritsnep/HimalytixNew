from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth import get_user_model
import os

# Import both default data scripts
from scripts.create_default_data import create_default_data

class Command(BaseCommand):
    help = "Sets up all system defaults: superuser, permissions, roles (Admin, Clerk, Manager, Auditor, User), accounting, and organization data."

    def handle(self, *args, **options):
        User = get_user_model()
        try:
            if not User.objects.filter(is_superuser=True).exists():
                username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
                email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
                password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
                if not (username and email and password):
                    self.stdout.write(self.style.WARNING(
                        'Superuser credentials not set in environment variables. Using defaults: admin/admin@example.com/admin.'
                    ))
                    username = 'admin'
                    email = 'admin@example.com'
                    password = 'admin'
                self.stdout.write(f"Creating default superuser '{username}'...")
                User.objects.create_superuser(username=username, email=email, password=password)
            else:
                self.stdout.write('Superuser already exists, skipping creation.')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error creating superuser: {e}"))

        try:
            self.stdout.write('Generating permissions for all models...')
            call_command('generate_permissions')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error generating permissions: {e}"))

        try:
            self.stdout.write('Setting up default roles for all organizations...')
            call_command('setup_default_roles')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error setting up default roles: {e}"))

        try:
            self.stdout.write('Setting up system roles for all organizations...')
            call_command('setup_system_roles')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error setting up system roles: {e}"))

        self.stdout.write(self.style.WARNING(
            'WARNING: Both Nepal-specific and generic accounting defaults will be created. This may result in duplicate or overlapping data. Review create_default_data for potential overlap.'
        ))

        try:
            self.stdout.write('Creating Nepal-specific default data...')
            create_default_data()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error creating Nepal-specific default data: {e}"))

        # NOTE: create_defaults() has been removed. All default/demo data is now seeded by create_default_data.py only.
        # If you need to add more demo data, extend create_default_data.py.

        self.stdout.write(self.style.SUCCESS('All system defaults have been set up successfully!')) 