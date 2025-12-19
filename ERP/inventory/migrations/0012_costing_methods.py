from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('Inventory', '0011_alter_inventoryitem_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='costing_method',
            field=models.CharField(
                choices=[
                    ('weighted_average', 'Weighted Average'),
                    ('fifo', 'FIFO'),
                    ('lifo', 'LIFO'),
                    ('standard', 'Standard Cost'),
                ],
                default='weighted_average',
                help_text='Choose how this product is valued during inventory movements.',
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='standard_cost',
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                help_text='Required for standard costing; used as the issue unit cost.',
                max_digits=19,
                null=True,
            ),
        ),
        migrations.CreateModel(
            name='CostLayer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reference_id', models.CharField(blank=True, max_length=100)),
                ('quantity_received', models.DecimalField(decimal_places=4, max_digits=15)),
                ('quantity_available', models.DecimalField(decimal_places=4, max_digits=15)),
                ('unit_cost', models.DecimalField(decimal_places=4, max_digits=19)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('batch', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='Inventory.batch')),
                ('location', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='Inventory.location')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='Inventory.product')),
                ('warehouse', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='Inventory.warehouse')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='usermanagement.Organization')),
            ],
            options={
                'ordering': ['created_at'],
                'indexes': [
                    models.Index(
                        fields=['organization', 'product', 'warehouse'],
                        name='inv_costlayer_org_prod_wh'
                    ),
                ],
            },
        ),
    ]
