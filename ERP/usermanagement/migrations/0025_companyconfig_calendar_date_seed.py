from django.db import migrations, models
import utils.calendars


class Migration(migrations.Migration):

    dependencies = [
        ('usermanagement', '0024_companyconfig_calendar_mode'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyconfig',
            name='calendar_date_seed',
            field=models.CharField(
                choices=utils.calendars.DateSeedStrategy.choices(),
                default=utils.calendars.DateSeedStrategy.DEFAULT,
                help_text='Prefill dates with today or the last entry (per org).',
                max_length=20,
            ),
        ),
    ]
