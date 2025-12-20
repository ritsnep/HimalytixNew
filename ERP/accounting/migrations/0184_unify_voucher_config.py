from django.db import migrations, models
import django.db.models.deletion


def wipe_legacy_voucher_configs(apps, schema_editor):
    VoucherModeConfig = apps.get_model('accounting', 'VoucherModeConfig')
    VoucherModeDefault = apps.get_model('accounting', 'VoucherModeDefault')
    VoucherConfiguration = apps.get_model('accounting', 'VoucherConfiguration')

    VoucherModeDefault.objects.all().delete()
    VoucherModeConfig.objects.all().delete()
    VoucherConfiguration.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0183_alter_purchaseordervoucher_voucher_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='vouchermodeconfig',
            name='module',
            field=models.CharField(
                choices=[
                    ('accounting', 'Accounting'),
                    ('banking', 'Banking'),
                    ('cash', 'Cash'),
                    ('sales', 'Sales'),
                    ('purchasing', 'Purchasing'),
                    ('inventory', 'Inventory'),
                    ('billing', 'Billing'),
                    ('pos', 'Point of Sale'),
                    ('manufacturing', 'Manufacturing'),
                    ('hr', 'Human Resources'),
                    ('other', 'Other'),
                ],
                default='accounting',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='vouchermodeconfig',
            name='affects_gl',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='vouchermodeconfig',
            name='affects_inventory',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='vouchermodeconfig',
            name='requires_approval',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='vouchermodeconfig',
            name='schema_definition',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='vouchermodeconfig',
            name='workflow_definition',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name='vouchermodeconfig',
            name='code',
            field=models.CharField(max_length=50),
        ),
        migrations.AlterField(
            model_name='vouchermodeconfig',
            name='ui_schema',
            field=models.JSONField(blank=True, default=dict, help_text='Deprecated: legacy UI schema (kept empty).'),
        ),
        migrations.AlterField(
            model_name='purchaseordervoucher',
            name='configuration',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='%(class)s_vouchers',
                to='accounting.vouchermodeconfig',
            ),
        ),
        migrations.AlterField(
            model_name='purchasereturnvoucher',
            name='configuration',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='%(class)s_vouchers',
                to='accounting.vouchermodeconfig',
            ),
        ),
        migrations.AlterField(
            model_name='salesordervoucher',
            name='configuration',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='%(class)s_vouchers',
                to='accounting.vouchermodeconfig',
            ),
        ),
        migrations.RunPython(wipe_legacy_voucher_configs, migrations.RunPython.noop),
        migrations.DeleteModel(
            name='VoucherConfiguration',
        ),
    ]
