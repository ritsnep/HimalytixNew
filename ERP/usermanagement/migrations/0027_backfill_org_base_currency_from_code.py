"""
Backfill Organization.base_currency_code by converting old string currency codes to FK references.

This migration expects that a Currency row exists for every currency code stored in the previous
`base_currency_code` field. It attempts to match by 'currency_code' and sets the FK accordingly.
If it cannot find a matching Currency record, the organization's base_currency_code remains null.
"""
from django.db import migrations


def backfill_org_base_currency(apps, schema_editor):
    Organization = apps.get_model('usermanagement', 'Organization')
    Currency = apps.get_model('accounting', 'Currency')

    for org in Organization.objects.all():
        # Get raw value as stored before field alter
        raw_value = None
        try:
            raw_value = org.__dict__.get('base_currency_code')
        except Exception:
            raw_value = None

        if not raw_value:
            continue

        # If raw_value is already a valid foreign key to accounting.currency, skip
        if Currency.objects.filter(pk=raw_value).exists():
            continue

        # raw_value might be a currency code string (e.g., 'USD'). Attempt to find matching currency.
        candidate = Currency.objects.filter(currency_code=str(raw_value)).first()
        if candidate:
            org.base_currency_code = candidate
            org.save(update_fields=['base_currency_code'])


class Migration(migrations.Migration):
    dependencies = [
        ('usermanagement', '0026_alter_organization_base_currency_code'),
        ('accounting', '0162_set_default_currency_data'),
    ]

    operations = [
        migrations.RunPython(backfill_org_base_currency, reverse_code=migrations.RunPython.noop),
    ]
