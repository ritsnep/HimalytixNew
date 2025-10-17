from django.db import migrations, models


def set_defaults(apps, schema_editor):
    AccountType = apps.get_model('accounting', 'AccountType')
    defaults = {
        'asset': ('1000', 100),
        'liability': ('2000', 100),
        'equity': ('3000', 100),
        'income': ('4000', 100),
        'expense': ('5000', 100),
    }
    for at in AccountType.objects.all():
        prefix, step = defaults.get(at.nature, ('9000', 100))
        if not at.root_code_prefix:
            at.root_code_prefix = prefix
        if not at.root_code_step:
            at.root_code_step = step
        at.save()


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0009_alter_journaltype_options_fiscalyear_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='accounttype',
            name='root_code_prefix',
            field=models.CharField(blank=True, help_text='Starting prefix for top level account codes', max_length=10, null=True),
        ),
        migrations.AddField(
            model_name='accounttype',
            name='root_code_step',
            field=models.PositiveIntegerField(default=100, help_text='Increment step for generating top level codes'),
        ),
        migrations.RunPython(set_defaults, migrations.RunPython.noop),
    ]