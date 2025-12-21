from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounting", "0001_initial"),
        ("usermanagement", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="VoucherConfigMaster",
            fields=[
                ("config_id", models.BigAutoField(primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=50)),
                ("label", models.CharField(max_length=200)),
                ("voucher_date_label", models.CharField(default="Date", max_length=100)),
                ("entry_date_label", models.CharField(blank=True, max_length=100)),
                ("ref_no_label", models.CharField(blank=True, max_length=100)),
                ("use_ref_no", models.BooleanField(default=True)),
                ("show_time", models.BooleanField(default=False)),
                ("show_document_details", models.BooleanField(default=False)),
                ("numbering_method", models.CharField(choices=[("auto", "Auto"), ("manual", "Manual")], default="auto", max_length=20)),
                ("auto_post", models.BooleanField(default=False)),
                ("prevent_duplicate_voucher_no", models.BooleanField(default=True)),
                ("affects_gl", models.BooleanField(default=True)),
                ("affects_inventory", models.BooleanField(default=False)),
                ("requires_approval", models.BooleanField(default=False)),
                ("schema_definition", models.JSONField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_voucher_config_masters",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_voucher_config_masters",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "journal_type",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="voucher_config_masters",
                        to="accounting.journaltype",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        db_column="organization_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="voucher_config_masters",
                        to="usermanagement.organization",
                    ),
                ),
            ],
            options={
                "db_table": "voucher_config_master",
                "ordering": ("organization_id", "code"),
                "unique_together": {("organization", "code")},
            },
        ),
        migrations.CreateModel(
            name="InventoryLineConfig",
            fields=[
                ("config_id", models.BigAutoField(primary_key=True, serialize=False)),
                ("show_rate", models.BooleanField(default=True)),
                ("show_amount", models.BooleanField(default=True)),
                ("allow_free_qty", models.BooleanField(default=False)),
                ("show_alternate_unit", models.BooleanField(default=False)),
                ("show_discount", models.BooleanField(default=False)),
                ("show_batch_no", models.BooleanField(default=False)),
                ("show_mfg_date", models.BooleanField(default=False)),
                ("show_exp_date", models.BooleanField(default=False)),
                ("show_serial_no", models.BooleanField(default=False)),
                ("qty_decimal_places", models.PositiveSmallIntegerField(default=2)),
                ("rate_decimal_places", models.PositiveSmallIntegerField(default=2)),
                ("is_fixed_product", models.BooleanField(default=False)),
                ("allow_batch_in_stock_journal", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "voucher_config",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="inventory_line_config",
                        to="voucher_config.voucherconfigmaster",
                    ),
                ),
            ],
            options={
                "db_table": "voucher_inventory_line_config",
            },
        ),
        migrations.CreateModel(
            name="FooterChargeSetup",
            fields=[
                ("footer_charge_id", models.BigAutoField(primary_key=True, serialize=False)),
                ("calculation_type", models.CharField(choices=[("rate", "Rate"), ("amount", "Amount")], default="rate", max_length=20)),
                ("rate", models.DecimalField(blank=True, decimal_places=4, max_digits=9, null=True)),
                ("amount", models.DecimalField(blank=True, decimal_places=4, max_digits=19, null=True)),
                ("can_edit", models.BooleanField(default=False)),
                ("display_order", models.PositiveSmallIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "ledger",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="voucher_footer_charges",
                        to="accounting.chartofaccount",
                    ),
                ),
                (
                    "voucher_config",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="footer_charges",
                        to="voucher_config.voucherconfigmaster",
                    ),
                ),
            ],
            options={
                "db_table": "voucher_footer_charge_setup",
                "ordering": ("display_order", "footer_charge_id"),
            },
        ),
        migrations.AddIndex(
            model_name="voucherconfigmaster",
            index=models.Index(fields=["organization", "code"], name="vcm_org_code_idx"),
        ),
    ]
