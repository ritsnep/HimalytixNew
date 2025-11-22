from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounting", "0132_accountingperiod_organization"),
    ]

    operations = [
        migrations.AddField(
            model_name="salesinvoice",
            name="ird_digital_payment_amount",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=19, null=True),
        ),
        migrations.AddField(
            model_name="salesinvoice",
            name="ird_digital_payment_txn_id",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="salesinvoice",
            name="ird_fiscal_year_code",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AddField(
            model_name="salesinvoice",
            name="ird_is_realtime",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="salesinvoice",
            name="ird_last_printed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="salesinvoice",
            name="ird_last_reprint_reason",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="salesinvoice",
            name="ird_reprint_count",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
