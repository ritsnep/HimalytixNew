"""
Database Indexes Migration - Phase 3 Task 5

Adds recommended database indexes for performance optimization.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0001_initial'),  # Update to your latest migration
    ]

    operations = [
        # Journal indexes
        migrations.AddIndex(
            model_name='journal',
            index=models.Index(fields=['organization_id', 'date'], name='idx_journal_org_date'),
        ),
        migrations.AddIndex(
            model_name='journal',
            index=models.Index(fields=['organization_id', 'status'], name='idx_journal_org_status'),
        ),
        migrations.AddIndex(
            model_name='journal',
            index=models.Index(fields=['organization_id', 'created_at'], name='idx_journal_org_created'),
        ),
        
        # JournalLine indexes
        migrations.AddIndex(
            model_name='journalline',
            index=models.Index(fields=['account_id', 'journal__date'], name='idx_line_account_date'),
        ),
        migrations.AddIndex(
            model_name='journalline',
            index=models.Index(fields=['journal_id'], name='idx_line_journal'),
        ),
        
        # Account indexes
        migrations.AddIndex(
            model_name='account',
            index=models.Index(fields=['organization_id', 'code'], name='idx_account_org_code'),
        ),
        migrations.AddIndex(
            model_name='account',
            index=models.Index(fields=['organization_id', 'account_type'], name='idx_account_type'),
        ),
        
        # ApprovalLog indexes (if exists)
        # migrations.AddIndex(
        #     model_name='approvallog',
        #     index=models.Index(fields=['organization_id', 'status'], name='idx_approval_org_status'),
        # ),
    ]
