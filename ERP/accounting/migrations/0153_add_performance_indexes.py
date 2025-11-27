# Generated migration for performance optimization
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0152_rename_accountingperiod_org_status_idx_accounting__organiz_097bfc_idx_and_more'),
    ]

    operations = [
        # Journal indexes for common queries
        migrations.AddIndex(
            model_name='journal',
            index=models.Index(fields=['organization', 'journal_date', 'status'], name='perf_journal_org_date_status'),
        ),
        migrations.AddIndex(
            model_name='journal',
            index=models.Index(fields=['organization', 'status'], name='perf_journal_org_status'),
        ),
        migrations.AddIndex(
            model_name='journal',
            index=models.Index(fields=['journal_date'], name='perf_journal_date'),
        ),
        migrations.AddIndex(
            model_name='journal',
            index=models.Index(fields=['status'], name='perf_journal_status'),
        ),
        migrations.AddIndex(
            model_name='journal',
            index=models.Index(fields=['period'], name='perf_journal_period'),
        ),
        
        # GeneralLedger indexes for balance queries
        migrations.AddIndex(
            model_name='generalledger',
            index=models.Index(fields=['organization_id', 'period'], name='perf_gl_org_period'),
        ),
        migrations.AddIndex(
            model_name='generalledger',
            index=models.Index(fields=['account', 'period'], name='perf_gl_account_period'),
        ),
        
        # ChartOfAccount indexes
        migrations.AddIndex(
            model_name='chartofaccount',
            index=models.Index(fields=['organization', 'account_code'], name='perf_coa_org_code'),
        ),
        migrations.AddIndex(
            model_name='chartofaccount',
            index=models.Index(fields=['organization', 'account_type'], name='perf_coa_org_type'),
        ),
        
        # JournalLine indexes for line item queries
        migrations.AddIndex(
            model_name='journalline',
            index=models.Index(fields=['journal'], name='perf_jl_journal'),
        ),
        migrations.AddIndex(
            model_name='journalline',
            index=models.Index(fields=['account'], name='perf_jl_account'),
        ),
    ]
