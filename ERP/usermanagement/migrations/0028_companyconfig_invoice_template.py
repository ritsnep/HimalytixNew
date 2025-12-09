from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usermanagement', '0027_backfill_org_base_currency_from_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyconfig',
            name='invoice_logo_url',
            field=models.URLField(blank=True, default='', help_text='Optional logo URL for printed invoices.'),
        ),
        migrations.AddField(
            model_name='companyconfig',
            name='invoice_template',
            field=models.CharField(choices=[('a4', 'A4 (Full Page)'), ('thermal', 'Thermal (80mm)')], default='a4', help_text='Choose the print layout used for sales invoices.', max_length=20),
        ),
    ]

