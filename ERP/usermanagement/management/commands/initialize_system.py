from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth import get_user_model
from scripts.create_default_data import create_default_data
import os

class Command(BaseCommand):
    help = "Initializes system permissions, roles and default accounting data"

    def handle(self, *args, **options):
        User = get_user_model()
        if not User.objects.filter(is_superuser=True).exists():
            username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
            email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
            password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin')
            self.stdout.write(f"Creating default superuser '{username}'...")
            User.objects.create_superuser(username=username, email=email, password=password)
        else:
            self.stdout.write('Superuser already exists, skipping creation.')

        call_command('generate_permissions')
        call_command('setup_default_roles')
        create_default_data()
        self.stdout.write(self.style.SUCCESS('System initialization complete.'))