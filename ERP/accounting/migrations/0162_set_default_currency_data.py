"""
Data migration to ensure at least one Currency has isdefault=True.

If no currency is marked as default, the migration will set the currency with code 'USD'
as the default; otherwise it will select the first active currency.
"""
from django.db import migrations


def set_default_currency(apps, schema_editor):
    Currency = apps.get_model('accounting', 'Currency')
    if Currency.objects.filter(isdefault=True).exists():
        return
    default_currency = Currency.objects.filter(currency_code='USD').first()
    if not default_currency:
        default_currency = Currency.objects.filter(is_active=True).first()
    if default_currency:
        default_currency.isdefault = True
        default_currency.save(update_fields=['isdefault'])


class Migration(migrations.Migration):
    dependencies = [
        ('accounting', '0161_currency_isdefault_currency_unique_default_currency'),
    ]

    operations = [
        migrations.RunPython(set_default_currency, reverse_code=migrations.RunPython.noop),
    ]
