"""
Management command to seed the database with all default data.

Usage:
    python manage.py seed_database
    python manage.py seed_database --skip-demo  # Skip demo journal entry
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Seeds the database with all default data for a fresh ERP setup'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-demo',
            action='store_true',
            help='Skip creating demo journal entry',
        )

    def handle(self, *args, **options):
        from scripts.seed_database import seed_all
        
        self.stdout.write(self.style.NOTICE('Starting database seed...'))
        
        try:
            seed_all()
            self.stdout.write(self.style.SUCCESS('Database seed completed successfully!'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error during seed: {e}'))
            raise
