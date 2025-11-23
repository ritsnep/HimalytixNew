from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "0138_monthlyjournallinesummary_and_more"),
        ("enterprise", "0003_fixedasset_accounts_and_status"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PayComponent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=50)),
                ("name", models.CharField(max_length=150)),
                (
                    "component_type",
                    models.CharField(
                        choices=[
                            ("earning", "Earning"),
                            ("deduction", "Deduction"),
                            ("tax", "Tax"),
                            ("benefit", "Benefit"),
                        ],
                        default="earning",
                        max_length=20,
                    ),
                ),
                (
                    "amount_type",
                    models.CharField(
                        choices=[("fixed", "Fixed"), ("percent", "Percent of base")],
                        default="fixed",
                        max_length=20,
                    ),
                ),
                ("amount_value", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("is_taxable", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="pay_components",
                        to="accounting.chartofaccount",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="paycomponents",
                        to="usermanagement.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
                "unique_together": {("organization", "code")},
            },
        ),
        migrations.CreateModel(
            name="PayrollRun",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("period_start", models.DateField()),
                ("period_end", models.DateField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("approved", "Approved"),
                            ("posted", "Posted"),
                        ],
                        default="draft",
                        max_length=20,
                    ),
                ),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("posted_at", models.DateTimeField(blank=True, null=True)),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="approved_payroll_runs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "expense_account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="payroll_expense_runs",
                        to="accounting.chartofaccount",
                    ),
                ),
                (
                    "liability_account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="payroll_liability_runs",
                        to="accounting.chartofaccount",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payrollruns",
                        to="usermanagement.organization",
                    ),
                ),
                (
                    "payroll_cycle",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="runs",
                        to="enterprise.payrollcycle",
                    ),
                ),
            ],
            options={
                "ordering": ["-period_end"],
            },
        ),
        migrations.CreateModel(
            name="PayrollRunLine",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("amount", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("notes", models.CharField(blank=True, max_length=255)),
                (
                    "component",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="payroll_run_lines",
                        to="enterprise.paycomponent",
                    ),
                ),
                (
                    "employee",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payroll_run_lines",
                        to="enterprise.employee",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payrollrunlines",
                        to="usermanagement.organization",
                    ),
                ),
                (
                    "payroll_run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lines",
                        to="enterprise.payrollrun",
                    ),
                ),
            ],
            options={
                "ordering": ["employee__last_name", "component__name"],
            },
        ),
        migrations.AddField(
            model_name="payrollentry",
            name="payroll_run",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="entries",
                to="enterprise.payrollrun",
            ),
        ),
    ]
