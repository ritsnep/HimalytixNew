# Generated migration for IRD e-billing fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0153_add_performance_indexes'),
    ]

    operations = [
        # Add IRD signature field if not exists
        migrations.AddField(
            model_name='salesinvoice',
            name='ird_signature',
            field=models.CharField(max_length=512, null=True, blank=True),
        ),
        # Add IRD acknowledgment ID
        migrations.AddField(
            model_name='salesinvoice',
            name='ird_ack_id',
            field=models.CharField(max_length=100, null=True, blank=True),
        ),
        # Add IRD status tracking
        migrations.AddField(
            model_name='salesinvoice',
            name='ird_status',
            field=models.CharField(
                max_length=50,
                null=True,
                blank=True,
                choices=[
                    ('pending', 'Pending'),
                    ('synced', 'Synced'),
                    ('failed', 'Failed'),
                    ('cancelled', 'Cancelled'),
                ],
            ),
        ),
        # Add IRD last response JSON
        migrations.AddField(
            model_name='salesinvoice',
            name='ird_last_response',
            field=models.JSONField(default=dict, blank=True),
        ),
        # Add IRD submission timestamp
        migrations.AddField(
            model_name='salesinvoice',
            name='ird_last_submitted_at',
            field=models.DateTimeField(null=True, blank=True),
        ),
        # Add reprint tracking
        migrations.AddField(
            model_name='salesinvoice',
            name='ird_reprint_count',
            field=models.PositiveIntegerField(default=0),
        ),
        # Add last printed timestamp
        migrations.AddField(
            model_name='salesinvoice',
            name='ird_last_printed_at',
            field=models.DateTimeField(null=True, blank=True),
        ),
        # Add fiscal year code in BS format
        migrations.AddField(
            model_name='salesinvoice',
            name='ird_fiscal_year_code',
            field=models.CharField(max_length=20, blank=True, default=''),
        ),
        # Add real-time sync flag
        migrations.AddField(
            model_name='salesinvoice',
            name='ird_is_realtime',
            field=models.BooleanField(default=True),
        ),
        # Add digital payment tracking
        migrations.AddField(
            model_name='salesinvoice',
            name='ird_digital_payment_amount',
            field=models.DecimalField(max_digits=19, decimal_places=4, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='salesinvoice',
            name='ird_digital_payment_txn_id',
            field=models.CharField(max_length=100, blank=True, default=''),
        ),
        # Add last reprint reason
        migrations.AddField(
            model_name='salesinvoice',
            name='ird_last_reprint_reason',
            field=models.CharField(max_length=255, blank=True, default=''),
        ),
        # Add indexes for IRD queries
        migrations.AddIndex(
            model_name='salesinvoice',
            index=models.Index(fields=['organization', 'ird_status'], name='sales_inv_ird_status_idx'),
        ),
        migrations.AddIndex(
            model_name='salesinvoice',
            index=models.Index(fields=['ird_ack_id'], name='sales_inv_ird_ack_idx'),
        ),
    ]
