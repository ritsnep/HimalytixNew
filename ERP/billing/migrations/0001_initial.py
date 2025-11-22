from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
from decimal import Decimal


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("usermanagement", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="InvoiceSeries",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fiscal_year", models.CharField(max_length=16)),
                ("current_number", models.PositiveIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="invoice_series", to="usermanagement.organization"),
                ),
            ],
            options={
                "ordering": ["tenant", "-fiscal_year"],
                "unique_together": {("tenant", "fiscal_year")},
            },
        ),
        migrations.CreateModel(
            name="InvoiceHeader",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("invoice_number", models.CharField(max_length=32)),
                ("fiscal_year", models.CharField(blank=True, max_length=16)),
                ("invoice_date", models.DateField(default=django.utils.timezone.now)),
                ("customer_name", models.CharField(max_length=255)),
                ("customer_pan", models.CharField(max_length=32)),
                ("customer_vat", models.CharField(blank=True, max_length=32, null=True)),
                ("billing_address", models.TextField(blank=True, default="")),
                ("payment_method", models.CharField(default="cash", max_length=64)),
                ("taxable_amount", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=19)),
                ("vat_amount", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=19)),
                ("total_amount", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=19)),
                (
                    "sync_status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("synced", "Synced"), ("failed", "Failed"), ("canceled", "Canceled")],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("canceled", models.BooleanField(default=False)),
                ("canceled_reason", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "series",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="invoices", to="billing.invoiceseries"),
                ),
                (
                    "tenant",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="billing_invoices", to="usermanagement.organization"),
                ),
            ],
            options={
                "ordering": ("-invoice_date", "-id"),
                "unique_together": {("tenant", "invoice_number")},
            },
        ),
        migrations.CreateModel(
            name="InvoiceAuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(choices=[("create", "Create"), ("cancel", "Cancel"), ("print", "Print"), ("export", "Export"), ("sync", "Sync"), ("note", "Credit/Debit Note")], max_length=32)),
                ("description", models.TextField(blank=True, default="")),
                ("timestamp", models.DateTimeField(auto_now_add=True)),
                (
                    "invoice",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_logs", to="billing.invoiceheader"),
                ),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ("-timestamp",),
            },
        ),
        migrations.CreateModel(
            name="InvoiceLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("description", models.TextField()),
                ("quantity", models.DecimalField(decimal_places=4, default=Decimal("1"), max_digits=19)),
                ("unit_price", models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=19)),
                ("vat_rate", models.DecimalField(decimal_places=2, default=Decimal("13.0"), max_digits=5)),
                ("taxable_amount", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=19)),
                ("vat_amount", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=19)),
                ("line_total", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=19)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "invoice",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="billing.invoiceheader"),
                ),
            ],
            options={
                "ordering": ("invoice", "id"),
            },
        ),
        migrations.CreateModel(
            name="CreditDebitNote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("note_type", models.CharField(choices=[("credit", "Credit"), ("debit", "Debit")], max_length=6)),
                ("reason", models.TextField()),
                ("amount", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=19)),
                ("taxable_amount", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=19)),
                ("vat_amount", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=19)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "invoice",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="notes", to="billing.invoiceheader"),
                ),
            ],
            options={
                "ordering": ("-created_at",),
            },
        ),
    ]
