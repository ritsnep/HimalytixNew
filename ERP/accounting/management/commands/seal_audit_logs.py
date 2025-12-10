"""
Django management command to seal audit logs with hash-chaining for immutability.

Usage:
    python manage.py seal_audit_logs [--organization ORG_ID] [--days DAYS] [--force]
    
    --organization: Seal logs for specific organization (default: all)
    --days: Only seal logs older than N days (default: 1)
    --force: Skip confirmation prompt
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import timedelta

from accounting.models import AuditLog
from accounting.utils.audit_integrity import compute_content_hash
from usermanagement.models import Organization


class Command(BaseCommand):
    help = 'Seal audit logs with cryptographic hash-chaining for immutability verification'

    def add_arguments(self, parser):
        parser.add_argument(
            '--organization',
            type=int,
            help='Organization ID to seal logs for (default: all)'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=1,
            help='Only seal logs older than N days (default: 1)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Skip confirmation prompt'
        )

    def handle(self, *args, **options):
        # Build query
        cutoff_date = timezone.now() - timedelta(days=options['days'])
        logs = AuditLog.objects.filter(
            timestamp__lt=cutoff_date,
            is_immutable=False,  # Only seal unsealed logs
        ).order_by('timestamp')
        
        if options['organization']:
            try:
                org = Organization.objects.get(id=options['organization'])
                logs = logs.filter(organization=org)
                self.stdout.write(f"Sealing logs for organization: {org.name}")
            except Organization.DoesNotExist:
                raise CommandError(f"Organization {options['organization']} not found")
        else:
            self.stdout.write("Sealing logs for all organizations")
        
        count = logs.count()
        if count == 0:
            self.stdout.write(self.style.WARNING("No logs to seal"))
            return
        
        self.stdout.write(f"Found {count} logs to seal")
        
        if not options['force']:
            confirm = input(f"Seal {count} audit logs? (yes/no): ")
            if confirm.lower() != 'yes':
                self.stdout.write("Cancelled")
                return
        
        # Seal logs in transaction
        sealed_count = 0
        failed_count = 0
        
        prev_hash = None
        for i, log in enumerate(logs):
            try:
                # Compute hash of this record
                log_dict = {
                    'user_id': log.user_id,
                    'action': log.action,
                    'content_type_id': log.content_type_id,
                    'object_id': log.object_id,
                    'changes': log.changes,
                    'timestamp': log.timestamp,
                }
                
                log.content_hash = compute_content_hash(log_dict)
                log.previous_hash_id = prev_hash  # Link to previous
                log.is_immutable = True
                log.save(update_fields=['content_hash', 'previous_hash_id', 'is_immutable'])
                
                prev_hash = log.id  # For next iteration
                sealed_count += 1
                
                if (i + 1) % 100 == 0:
                    self.stdout.write(f"  Sealed {i + 1}/{count} logs...")
            
            except Exception as e:
                failed_count += 1
                self.stdout.write(self.style.ERROR(f"Failed to seal log {log.id}: {str(e)}"))
        
        self.stdout.write(self.style.SUCCESS(f"\n✓ Sealed {sealed_count} audit logs"))
        if failed_count > 0:
            self.stdout.write(self.style.WARNING(f"✗ Failed to seal {failed_count} logs"))
