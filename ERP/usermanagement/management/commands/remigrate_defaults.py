from django.core.management.base import BaseCommand
from django.core.management import call_command

from scripts.create_default_data import create_default_data

class Command(BaseCommand):
    help = "Flush database, run migrations, and load default data"

    def handle(self, *args, **options):
        self.stdout.write("Flushing database...")
        call_command('flush', interactive=False)
        self.stdout.write("Applying migrations...")
        call_command('migrate', interactive=False)
        self.stdout.write("Generating permissions...")
        call_command('generate_permissions')
        self.stdout.write("Setting up default roles...")
        call_command('setup_default_roles')
        self.stdout.write("Creating default data...")
        create_default_data()
        self.stdout.write(self.style.SUCCESS('Database remigrated with default data.'))
