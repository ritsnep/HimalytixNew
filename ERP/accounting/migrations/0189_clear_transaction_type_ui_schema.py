from django.db import migrations


def clear_ui_schema(apps, schema_editor):
    TransactionTypeConfig = apps.get_model("accounting", "TransactionTypeConfig")
    TransactionTypeConfig.objects.exclude(ui_schema={}).update(ui_schema={})


class Migration(migrations.Migration):
    dependencies = [
        ("accounting", "0188_voucher_process_persistence"),
    ]

    operations = [
        migrations.RunPython(clear_ui_schema, migrations.RunPython.noop),
    ]
