from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "0105_merge_20251025_0011"),
    ]

    operations = [
        migrations.AddField(
            model_name="journal",
            name="charges_data",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="journal",
            name="header_udf_data",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="journal",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
