from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "0150_alter_fiscalyear_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="accountingperiod",
            name="is_closed",
            field=models.BooleanField(
                default=False,
                help_text='Legacy flag mirrored from status == "closed".',
            ),
        ),
        migrations.AddIndex(
            model_name="accountingperiod",
            index=models.Index(
                fields=["organization", "status"],
                name="accountingperiod_org_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="accountingperiod",
            index=models.Index(
                fields=["organization", "is_closed"],
                name="accountingperiod_org_isclosed_idx",
            ),
        ),
    ]
