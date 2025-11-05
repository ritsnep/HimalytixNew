from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0110_create_reporting_functions'),
        ('usermanagement', '0022_alter_permission_action'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ReportDefinition',
            fields=[
                ('report_id', models.BigAutoField(primary_key=True, serialize=False)),
                ('code', models.CharField(max_length=100)),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('stored_procedure', models.CharField(help_text='Name of the database function or stored procedure to call.', max_length=255)),
                ('parameter_schema', models.JSONField(blank=True, default=dict, help_text='Declarative parameter definitions for dynamic parameter forms.')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_report_definitions', to=settings.AUTH_USER_MODEL)),
                ('organization', models.ForeignKey(blank=True, help_text='Optional organization scope; null makes the report available to every tenant.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='report_definitions', to='usermanagement.organization')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='updated_report_definitions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'report_definition',
                'ordering': ['organization_id', 'code'],
                'unique_together': {('organization', 'code')},
            },
        ),
    ]
