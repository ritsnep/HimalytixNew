from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "0138_monthlyjournallinesummary_and_more"),
        ("enterprise", "0002_alter_assetdepreciationschedule_organization_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="fixedassetcategory",
            name="accumulated_depreciation_account",
            field=models.ForeignKey(
                blank=True,
                help_text="Balance sheet contra-asset for accumulated depreciation.",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="enterprise_accumulated_depreciation_accounts",
                null=True,
                to="accounting.chartofaccount",
            ),
        ),
        migrations.AddField(
            model_name="fixedassetcategory",
            name="asset_account",
            field=models.ForeignKey(
                help_text="Balance sheet account to hold the asset cost.",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="enterprise_asset_accounts",
                blank=True,
                null=True,
                to="accounting.chartofaccount",
            ),
        ),
        migrations.AddField(
            model_name="fixedassetcategory",
            name="depreciation_expense_account",
            field=models.ForeignKey(
                help_text="Income statement account for depreciation expense.",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="enterprise_depreciation_expense_accounts",
                blank=True,
                null=True,
                to="accounting.chartofaccount",
            ),
        ),
        migrations.AddField(
            model_name="fixedassetcategory",
            name="disposal_gain_account",
            field=models.ForeignKey(
                blank=True,
                help_text="Optional account for gains on disposal.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="enterprise_disposal_gain_accounts",
                to="accounting.chartofaccount",
            ),
        ),
        migrations.AddField(
            model_name="fixedassetcategory",
            name="disposal_loss_account",
            field=models.ForeignKey(
                blank=True,
                help_text="Optional account for losses on disposal.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="enterprise_disposal_loss_accounts",
                to="accounting.chartofaccount",
            ),
        ),
        migrations.AddField(
            model_name="fixedasset",
            name="disposed_at",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="fixedasset",
            name="status",
            field=models.CharField(
                choices=[("active", "Active"), ("disposed", "Disposed")],
                default="active",
                max_length=20,
            ),
        ),
    ]
