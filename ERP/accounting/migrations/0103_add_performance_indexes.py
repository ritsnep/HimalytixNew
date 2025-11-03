from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0102_alter_fiscalyear_id'),
    ]

    operations = [
        # Create indexes idempotently at the DB level, and also record them in migration state
        migrations.RunSQL(
            sql=(
                "CREATE INDEX IF NOT EXISTS journal_org_date_status_idx ON accounting_journal (organization_id, journal_date, status);"
            ),
            reverse_sql=(
                "DROP INDEX IF EXISTS journal_org_date_status_idx;"
            ),
            state_operations=[
                migrations.AddIndex(
                    model_name='journal',
                    index=models.Index(fields=['organization', 'journal_date', 'status'], name='journal_org_date_status_idx'),
                ),
            ],
        ),
        migrations.RunSQL(
            sql=(
                "CREATE INDEX IF NOT EXISTS journal_date_idx ON accounting_journal (journal_date);"
            ),
            reverse_sql=(
                "DROP INDEX IF EXISTS journal_date_idx;"
            ),
            state_operations=[
                migrations.AddIndex(
                    model_name='journal',
                    index=models.Index(fields=['journal_date'], name='journal_date_idx'),
                ),
            ],
        ),
        migrations.RunSQL(
            sql=(
                "CREATE INDEX IF NOT EXISTS journal_status_idx ON accounting_journal (status);"
            ),
            reverse_sql=(
                "DROP INDEX IF EXISTS journal_status_idx;"
            ),
            state_operations=[
                migrations.AddIndex(
                    model_name='journal',
                    index=models.Index(fields=['status'], name='journal_status_idx'),
                ),
            ],
        ),
    ]
