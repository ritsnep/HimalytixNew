"""
Django management command to archive or delete old audit logs per retention policy.

Usage:
    python manage.py archive_audit_logs [--days DAYS] [--action archive|delete] [--dry-run]
    
    --days: Archive/delete logs older than N days (default: 365 = 1 year)
    --action: 'archive' (copy to archive table) or 'delete' (remove), default: archive
    --dry-run: Show what would happen without making changes
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import connection
from datetime import timedelta

from accounting.models import AuditLog


class Command(BaseCommand):
    help = 'Archive or delete old audit logs per retention policy'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=365,
            help='Archive/delete logs older than N days (default: 365)'
        )
        parser.add_argument(
            '--action',
            choices=['archive', 'delete'],
            default='archive',
            help='Action to perform: archive or delete (default: archive)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would happen without making changes'
        )

    def handle(self, *args, **options):
        days = options['days']
        action = options['action']
        dry_run = options['dry_run']
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        logs = AuditLog.objects.filter(timestamp__lt=cutoff_date)
        count = logs.count()
        
        if count == 0:
            self.stdout.write(self.style.WARNING(f"No logs older than {days} days to process"))
            return
        
        self.stdout.write(f"Found {count} logs older than {days} days (before {cutoff_date})")
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f"[DRY-RUN] Would {action} {count} logs"))
            # Show sample
            samples = logs[:5]
            for log in samples:
                self.stdout.write(f"  - {log.timestamp} | {log.user} | {log.action}")
            return
        
        # Confirm
        confirm = input(f"{action.upper()} {count} audit logs? (yes/no): ")
        if confirm.lower() != 'yes':
            self.stdout.write("Cancelled")
            return
        
        try:
            if action == 'delete':
                logs.delete()
                self.stdout.write(self.style.SUCCESS(f"✓ Deleted {count} audit logs"))
            
            elif action == 'archive':
                # Archive: copy to archive table if it exists, else create JSON export
                self._archive_logs(logs, count)
        
        except Exception as e:
            raise CommandError(f"Failed to {action} logs: {str(e)}")
    
    def _archive_logs(self, logs, count):
        """Archive logs to a separate table or JSON file."""
        # Option 1: Copy to audit_log_archive table if it exists
        # Option 2: Export to JSON file for long-term storage
        
        import json
        from datetime import datetime
        
        # For MVP, export to JSON file
        archive_filename = f'audit_archive_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        
        data = []
        for log in logs:
            data.append({
                'id': log.id,
                'timestamp': log.timestamp.isoformat(),
                'user': str(log.user) if log.user else None,
                'organization': str(log.organization) if log.organization else None,
                'action': log.action,
                'model': log.content_type.model if log.content_type else None,
                'object_id': log.object_id,
                'changes': log.changes,
                'details': log.details,
                'ip_address': log.ip_address,
                'content_hash': log.content_hash,
            })
        
        with open(archive_filename, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        # Delete after successful export
        logs.delete()
        
        self.stdout.write(self.style.SUCCESS(f"✓ Archived {count} logs to {archive_filename}"))
        self.stdout.write(f"  Location: {archive_filename}")
