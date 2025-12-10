import os
import subprocess
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import connection
from tenancy.models import Tenant

class Command(BaseCommand):
    help = 'Restore a tenant backup from a file. WARNING: This will overwrite existing data.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=str, required=True, help='Tenant code')
        parser.add_argument('--file', type=str, required=True, help='Path to backup file (.dump)')
        parser.add_argument('--force', action='store_true', help='Skip confirmation')

    def handle(self, *args, **options):
        tenant_code = options['tenant']
        file_path = options['file']
        force = options['force']

        if not os.path.exists(file_path):
            raise CommandError(f"Backup file not found: {file_path}")

        try:
            tenant = Tenant.objects.get(code=tenant_code)
        except Tenant.DoesNotExist:
            raise CommandError(f"Tenant with code {tenant_code} not found")

        schema_name = tenant.data_schema
        
        self.stdout.write(self.style.WARNING(f"Preparing to restore backup for tenant: {tenant.name} ({tenant.code})"))
        self.stdout.write(self.style.WARNING(f"Target Schema: {schema_name}"))
        self.stdout.write(self.style.WARNING(f"Source File: {file_path}"))
        self.stdout.write(self.style.ERROR("WARNING: THIS WILL DELETE ALL EXISTING DATA FOR THIS TENANT!"))

        if not force:
            confirm = input("Are you sure you want to continue? (yes/no): ")
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.SUCCESS("Operation cancelled."))
                return

        # Get DB config
        db_conf = settings.DATABASES['default']
        if 'postgresql' not in db_conf['ENGINE']:
            raise CommandError("Only PostgreSQL restore is supported currently")

        env = os.environ.copy()
        env['PGPASSWORD'] = db_conf['PASSWORD']

        # 1. Drop Schema
        self.stdout.write("Dropping existing schema...")
        with connection.cursor() as cursor:
            cursor.execute(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE")
            cursor.execute(f"CREATE SCHEMA {schema_name}")

        # 2. Run pg_restore
        # pg_restore -h host -p port -U user -d dbname -n schema -F c file
        # Note: The dump was created with -n schema, so it contains schema info.
        # However, if we want to restore to a DIFFERENT schema (e.g. for testing), we might need --no-owner --role=...
        # For now, assuming restoring to same schema name.
        
        cmd = [
            'pg_restore',
            '-h', db_conf['HOST'],
            '-p', str(db_conf['PORT']),
            '-U', db_conf['USER'],
            '-d', db_conf['NAME'],
            '-n', schema_name, # Only restore this schema
            '--clean', # Clean objects before creating
            '--if-exists',
            '--no-owner', # Skip ownership setting (often causes issues if users differ)
            '--no-privileges', # Skip privilege setting
            file_path
        ]

        self.stdout.write("Running pg_restore...")
        try:
            subprocess.run(cmd, env=env, check=True)
            self.stdout.write(self.style.SUCCESS(f"Successfully restored backup for {tenant.code}"))
        except subprocess.CalledProcessError as e:
            raise CommandError(f"pg_restore failed: {e}")
