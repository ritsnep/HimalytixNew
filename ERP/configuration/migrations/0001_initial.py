from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("usermanagement", "0030_add_auditlog_organization"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConfigurationEntry",
            fields=[
                ("entry_id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "scope",
                    models.CharField(
                        choices=[
                            ("core", "Core Platform"),
                            ("finance", "Finance"),
                            ("procurement", "Procurement"),
                            ("supply_chain", "Supply Chain"),
                            ("crm", "CRM"),
                            ("hr", "HR"),
                        ],
                        default="core",
                        max_length=64,
                    ),
                ),
                ("key", models.CharField(max_length=128)),
                ("value", models.JSONField(blank=True, default=dict)),
                ("description", models.TextField(blank=True)),
                ("is_sensitive", models.BooleanField(default=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "organization",
                    models.ForeignKey(
                        blank=True,
                        help_text="NULL represents a global configuration entry.",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="configuration_entries",
                        to="usermanagement.organization",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_configuration_entries",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "configuration_entry",
                "ordering": ("organization_id", "scope", "key"),
                "unique_together": {("organization", "scope", "key")},
            },
        ),
        migrations.CreateModel(
            name="FeatureToggle",
            fields=[
                ("toggle_id", models.BigAutoField(primary_key=True, serialize=False)),
                ("module", models.CharField(max_length=64)),
                ("key", models.CharField(max_length=128)),
                ("is_enabled", models.BooleanField(default=False)),
                ("description", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("starts_on", models.DateField(blank=True, null=True)),
                ("expires_on", models.DateField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.ForeignKey(
                        blank=True,
                        help_text="NULL entries apply globally to all organizations.",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="feature_toggles",
                        to="usermanagement.organization",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_feature_toggles",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "feature_toggle",
                "ordering": ("organization_id", "module", "key"),
                "unique_together": {("organization", "module", "key")},
            },
        ),
        migrations.AddIndex(
            model_name="configurationentry",
            index=models.Index(fields=("organization", "scope", "key"), name="cfg_scope_idx"),
        ),
        migrations.AddIndex(
            model_name="featuretoggle",
            index=models.Index(fields=("organization", "module", "key"), name="feature_toggle_idx"),
        ),
    ]
