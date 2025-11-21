from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "0127_alter_fiscalyear_id_taxcodegroup_invoicelinetax_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="journal",
            name="approved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="journal",
            name="approved_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="approved_journals",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="salesinvoice",
            name="ird_ack_id",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="salesinvoice",
            name="ird_last_response",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="salesinvoice",
            name="ird_last_submitted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="salesinvoice",
            name="ird_signature",
            field=models.CharField(blank=True, max_length=512, null=True),
        ),
        migrations.AddField(
            model_name="salesinvoice",
            name="ird_status",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
