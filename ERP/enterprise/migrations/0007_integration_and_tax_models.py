from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "0138_monthlyjournallinesummary_and_more"),
        ("enterprise", "0006_mrp_models"),
    ]

    operations = [
        migrations.CreateModel(
            name="IntegrationCredential",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=150)),
                (
                    "connector_type",
                    models.CharField(
                        choices=[
                            ("bank_feed", "Bank Feed"),
                            ("payment_gateway", "Payment Gateway"),
                            ("ecommerce", "E-commerce"),
                            ("logistics", "Logistics"),
                            ("pos", "Point of Sale"),
                        ],
                        max_length=50,
                    ),
                ),
                ("credential_blob", models.JSONField(blank=True, default=dict)),
                ("masked_display", models.CharField(blank=True, max_length=100)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="integrationcredentials",
                        to="usermanagement.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
                "unique_together": {("organization", "name")},
            },
        ),
        migrations.CreateModel(
            name="WebhookSubscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=150)),
                ("token", models.UUIDField(default=uuid.uuid4, unique=True)),
                ("source", models.CharField(blank=True, max_length=100)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="webhooksubscriptions",
                        to="usermanagement.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="TaxRegime",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=150)),
                ("country", models.CharField(blank=True, max_length=50)),
                ("region", models.CharField(blank=True, max_length=50)),
                ("e_invoice_format", models.CharField(blank=True, max_length=100)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="taxregimes",
                        to="usermanagement.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
            },
        ),
    ]
