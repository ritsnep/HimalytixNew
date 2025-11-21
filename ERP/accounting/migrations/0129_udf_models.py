from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "0128_journal_approval_and_salesinvoice_ird_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("contenttypes", "0002_remove_content_type_name"),
        ("usermanagement", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="UDFDefinition",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("field_name", models.CharField(help_text="Internal field name (no spaces)", max_length=50)),
                ("display_name", models.CharField(help_text="Field label", max_length=100)),
                ("field_type", models.CharField(choices=[("text", "Text"), ("number", "Number"), ("decimal", "Decimal"), ("date", "Date"), ("datetime", "DateTime"), ("boolean", "Boolean"), ("select", "Select"), ("multiselect", "MultiSelect"), ("json", "JSON")], default="text", max_length=20)),
                ("is_required", models.BooleanField(default=False)),
                ("is_filterable", models.BooleanField(default=False)),
                ("is_pivot_dim", models.BooleanField(default=False)),
                ("choices", models.JSONField(blank=True, help_text="For select/multiselect options", null=True)),
                ("default_value", models.CharField(blank=True, max_length=255, null=True)),
                ("help_text", models.TextField(blank=True, null=True)),
                ("min_value", models.DecimalField(blank=True, decimal_places=4, max_digits=19, null=True)),
                ("max_value", models.DecimalField(blank=True, decimal_places=4, max_digits=19, null=True)),
                ("min_length", models.IntegerField(blank=True, null=True)),
                ("max_length", models.IntegerField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("content_type", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="contenttypes.contenttype")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="udf_definitions", to="usermanagement.organization")),
            ],
            options={
                "db_table": "udf_definition",
                "ordering": ["content_type", "field_name"],
                "unique_together": {("content_type", "field_name", "organization")},
            },
        ),
        migrations.CreateModel(
            name="UDFValue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("object_id", models.PositiveIntegerField()),
                ("value", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("content_type", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="contenttypes.contenttype")),
                ("udf_definition", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="values", to="accounting.udfdefinition")),
            ],
            options={
                "db_table": "udf_value",
                "unique_together": {("udf_definition", "content_type", "object_id")},
            },
        ),
    ]
