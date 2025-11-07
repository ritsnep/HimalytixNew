# Generated manually for year-end closing enhancements
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "0114_alter_fiscalyear_id"),
        ("usermanagement", "0022_alter_permission_action"),
    ]

    operations = [
        migrations.CreateModel(
            name="AccountingSettings",
            fields=[
                ("settings_id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "statutory_framework",
                    models.CharField(
                        choices=[
                            ("ifrs", "IFRS"),
                            ("nfrs", "NFRS"),
                            ("gaap", "GAAP / Local GAAP"),
                        ],
                        default="ifrs",
                        help_text="Primary statutory reporting framework used for classifications.",
                        max_length=16,
                    ),
                ),
                (
                    "auto_rollover_closing",
                    models.BooleanField(
                        default=False,
                        help_text="Automatically generate opening balance journals after fiscal year close.",
                    ),
                ),
                (
                    "auto_fx_lookup",
                    models.BooleanField(
                        default=True,
                        help_text="Automatically hydrate exchange rates from CurrencyExchangeRate records when posting.",
                    ),
                ),
                (
                    "enable_currency_revaluation",
                    models.BooleanField(
                        default=False,
                        help_text="Run currency revaluation jobs during fiscal close.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "current_year_income_account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="accounting.chartofaccount",
                    ),
                ),
                (
                    "organization",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="accounting_settings",
                        to="usermanagement.organization",
                    ),
                ),
                (
                    "retained_earnings_account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="accounting.chartofaccount",
                    ),
                ),
            ],
            options={
                "db_table": "accounting_settings",
                "verbose_name_plural": "Accounting Settings",
            },
        ),
        migrations.AddConstraint(
            model_name="fiscalyear",
            constraint=models.UniqueConstraint(
                condition=models.Q(is_current=True),
                fields=("organization",),
                name="unique_current_fiscal_year_per_org",
            ),
        ),
        migrations.AddConstraint(
            model_name="fiscalyear",
            constraint=models.UniqueConstraint(
                condition=models.Q(is_default=True),
                fields=("organization",),
                name="unique_default_fiscal_year_per_org",
            ),
        ),
        migrations.AddConstraint(
            model_name="journal",
            constraint=models.CheckConstraint(
                check=(
                    ~models.Q(status="posted")
                    | models.Q(total_debit=models.F("total_credit"))
                ),
                name="journal_balanced_when_posted",
            ),
        ),
        migrations.AddConstraint(
            model_name="journalline",
            constraint=models.CheckConstraint(
                check=(
                    models.Q(debit_amount__gt=0, credit_amount=0)
                    | models.Q(credit_amount__gt=0, debit_amount=0)
                ),
                name="journalline_single_sided",
            ),
        ),
    ]
