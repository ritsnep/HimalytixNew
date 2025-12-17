from importlib import import_module

from django.db import migrations


def refresh_reporting_functions(apps, schema_editor):
    report_fx = import_module("accounting.migrations.0110_create_reporting_functions")
    report_fx.create_functions(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "0110_create_reporting_functions"),
    ]

    operations = [
        migrations.RunPython(
            refresh_reporting_functions,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
