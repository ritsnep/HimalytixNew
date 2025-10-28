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
        # Removed invalid index on non-existent 'date' field
        migrations.AddIndex(
            model_name='journal',
            index=models.Index(fields=['organization_id', 'status'], name='idx_journal_org_status'),
        ),
        migrations.AddIndex(
            model_name='journal',
            index=models.Index(fields=['organization_id', 'created_at'], name='idx_journal_org_created'),
        ),
        
        # JournalLine indexes
        # Removed invalid index on non-existent 'journal__date' field
        migrations.AddIndex(
            model_name='journalline',
            index=models.Index(fields=['journal_id'], name='idx_line_journal'),
        ),
        
        # Account indexes
        # Removed invalid indexes for non-existent 'account' model
            # Removed invalid index on non-existent 'date' field
        #     index=models.Index(fields=['organization_id', 'status'], name='idx_approval_org_status'),
        # ),
    ]
