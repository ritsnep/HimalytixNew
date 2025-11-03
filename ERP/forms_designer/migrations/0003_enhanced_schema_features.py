# Generated migration for enhanced forms designer features

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    # ('accounting', '0001_initial'),  # Removed hard dependency to avoid cross-app FK issues
        ('forms_designer', '0002_initial'),
    ]

    operations = [
        # Add new fields to VoucherSchema
        migrations.AddField(
            model_name='voucherschema',
            name='status',
            field=models.CharField(
                choices=[
                    ('draft', 'Draft'),
                    ('pending_approval', 'Pending Approval'),
                    ('approved', 'Approved'),
                    ('published', 'Published'),
                    ('rejected', 'Rejected'),
                    ('archived', 'Archived')
                ],
                default='draft',
                max_length=20
            ),
        ),
        migrations.AddField(
            model_name='voucherschema',
            name='is_active',
            field=models.BooleanField(default=False, help_text='Only one version can be active at a time'),
        ),
        migrations.AddField(
            model_name='voucherschema',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='voucherschema',
            name='updated_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='updated_schemas',
                to=settings.AUTH_USER_MODEL
            ),
        ),
        migrations.AddField(
            model_name='voucherschema',
            name='submitted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='voucherschema',
            name='submitted_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='submitted_schemas',
                to=settings.AUTH_USER_MODEL
            ),
        ),
        migrations.AddField(
            model_name='voucherschema',
            name='approved_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='voucherschema',
            name='approved_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='approved_schemas',
                to=settings.AUTH_USER_MODEL
            ),
        ),
        migrations.AddField(
            model_name='voucherschema',
            name='rejected_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='voucherschema',
            name='rejected_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='rejected_schemas',
                to=settings.AUTH_USER_MODEL
            ),
        ),
        migrations.AddField(
            model_name='voucherschema',
            name='rejection_reason',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='voucherschema',
            name='published_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='voucherschema',
            name='published_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='published_schemas',
                to=settings.AUTH_USER_MODEL
            ),
        ),
        migrations.AddField(
            model_name='voucherschema',
            name='change_notes',
            field=models.TextField(blank=True, help_text='Description of changes in this version', null=True),
        ),
        # Create SchemaTemplate model
        migrations.CreateModel(
            name='SchemaTemplate',
            fields=[
                ('template_id', models.AutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True, null=True)),
                ('category', models.CharField(
                    choices=[
                        ('standard', 'Standard'),
                        ('payment', 'Payment'),
                        ('receipt', 'Receipt'),
                        ('journal', 'Journal'),
                        ('custom', 'Custom')
                    ],
                    default='custom',
                    max_length=50
                )),
                ('schema', models.JSONField(help_text='Template schema structure')),
                ('is_system', models.BooleanField(default=False, help_text='System templates cannot be deleted')),
                ('is_public', models.BooleanField(default=False, help_text='Available to all organizations')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('usage_count', models.PositiveIntegerField(default=0)),
                ('created_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL
                )),
                ('organization_id', models.BigIntegerField(
                    blank=True,
                    null=True,
                    help_text='Organization ID if template is organization-specific'
                )),
            ],
            options={
                'db_table': 'forms_designer_schema_template',
                'ordering': ['category', 'name'],
            },
        ),
        # Update metadata
        migrations.AlterModelTable(
            name='voucherschema',
            table='forms_designer_voucher_schema',
        ),
        migrations.AddIndex(
            model_name='voucherschema',
            index=models.Index(fields=['voucher_mode_config', 'status'], name='forms_desig_voucher_idx1'),
        ),
        migrations.AddIndex(
            model_name='voucherschema',
            index=models.Index(fields=['voucher_mode_config', 'is_active'], name='forms_desig_voucher_idx2'),
        ),
        migrations.AlterField(
            model_name='voucherschema',
            name='created_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='created_schemas',
                to=settings.AUTH_USER_MODEL
            ),
        ),
    ]
