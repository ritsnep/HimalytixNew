from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("enterprise", "0004_payroll_components_and_runs"),
    ]

    operations = [
        migrations.AddField(
            model_name="budget",
            name="revision_label",
            field=models.CharField(default="v1", max_length=50),
        ),
        migrations.AddField(
            model_name="budget",
            name="revision_of",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=migrations.deletion.SET_NULL,
                related_name="revisions",
                to="enterprise.budget",
            ),
        ),
    ]
