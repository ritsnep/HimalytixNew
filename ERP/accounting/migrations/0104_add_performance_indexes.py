from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0103_alter_fiscalyear_id'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='journal',
            index=models.Index(fields=['organization', 'journal_date', 'status'], name='journal_org_date_status_idx'),
        ),
        migrations.AddIndex(
            model_name='journal',
            index=models.Index(fields=['journal_date'], name='journal_date_idx'),
        ),
        migrations.AddIndex(
            model_name='journal',
            index=models.Index(fields=['status'], name='journal_status_idx'),
        ),
    ]
