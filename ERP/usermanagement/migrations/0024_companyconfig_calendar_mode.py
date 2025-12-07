from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usermanagement', '0023_organization_address_organization_fiscal_year_start_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyconfig',
            name='calendar_mode',
            field=models.CharField(
                choices=[('AD', 'Gregorian (AD only)'), ('BS', 'Bikram Sambat (BS only)'), ('DUAL', 'Dual (toggle AD/BS)')],
                default='AD',
                help_text='Default calendar experience for the organization.',
                max_length=10,
            ),
        ),
    ]
