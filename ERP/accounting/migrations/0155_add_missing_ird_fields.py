# Generated migration to add missing IRD and cancellation fields to SalesInvoice
from django.db import migrations, models
from django.conf import settings
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0154_salesinvoice_ird_fields'),
    ]

    operations = [
        # Alter ird_signature to TextField
        migrations.AlterField(
            model_name='salesinvoice',
            name='ird_signature',
            field=models.TextField(null=True, blank=True),
        ),
        # Alter ird_status to include choices and default
        migrations.AlterField(
            model_name='salesinvoice',
            name='ird_status',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('pending', 'Pending'),
                    ('synced', 'Synced'),
                    ('failed', 'Failed'),
                    ('cancelled', 'Cancelled'),
                ],
                default='pending',
                null=True,
                blank=True,
            ),
        ),
        # Ensure ird_last_response accepts null
        migrations.AlterField(
            model_name='salesinvoice',
            name='ird_last_response',
            field=models.JSONField(default=dict, blank=True, null=True),
        ),
        # Add QR data field
        migrations.AddField(
            model_name='salesinvoice',
            name='ird_qr_data',
            field=models.CharField(max_length=500, blank=True, null=True),
        ),
        # Cancellation tracking
        migrations.AddField(
            model_name='salesinvoice',
            name='cancelled_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='salesinvoice',
            name='cancellation_reason',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='salesinvoice',
            name='cancelled_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cancelled_invoices', to=settings.AUTH_USER_MODEL),
        ),
        # Indexes
        migrations.AddIndex(
            model_name='salesinvoice',
            index=models.Index(fields=['organization', 'ird_status'], name='accounting_salesinvoice_org_ird_status_idx'),
        ),
        migrations.AddIndex(
            model_name='salesinvoice',
            index=models.Index(fields=['ird_ack_id'], name='accounting_salesinvoice_ird_ack_idx'),
        ),
    ]
