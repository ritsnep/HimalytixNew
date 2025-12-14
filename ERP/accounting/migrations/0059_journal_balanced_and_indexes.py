"""Add is_balanced to Journal and indexes for performance

Revision ID: 0059_journal_balanced_and_indexes
Revises: 0058_auto_previous
Create Date: 2025-12-14 00:00
"""
from django.db import migrations, models
import django.db.models.deletion
from django.contrib.postgres.indexes import GinIndex


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0058_auto_previous'),
    ]

    operations = [
        # Add is_balanced field to Journal
        migrations.AddField(
            model_name='journal',
            name='is_balanced',
            field=models.BooleanField(default=True, db_index=True),
        ),

        # Add composite index on (status, is_balanced) for fast filtering of drafts/unbalanced
        migrations.AddIndex(
            model_name='journal',
            index=models.Index(fields=['status', 'is_balanced'], name='journal_status_bal_idx'),
        ),

        # Add index on journalline (account, journal)
        migrations.AddIndex(
            model_name='journalline',
            index=models.Index(fields=['account', 'journal'], name='journalline_account_journal_idx'),
        ),

        # Add GIN index on udf_data for JSON queries (Postgres only)
        migrations.AddIndex(
            model_name='journalline',
            index=GinIndex(fields=['udf_data'], name='journalline_udfdata_gin'),
        ),

        # Data migration: backfill is_balanced from totals
        migrations.RunSQL(
            sql=(
                "UPDATE accounting_journal SET is_balanced = (total_debit = total_credit) WHERE is_balanced IS DISTINCT FROM (total_debit = total_credit);"
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
