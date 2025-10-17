from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='EntityProperty',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('entity_name', models.CharField(db_index=True, max_length=100)),
                ('property_name', models.CharField(max_length=100)),
                ('data_type', models.CharField(max_length=50)),
                ('label', models.CharField(max_length=100)),
                ('validation_rules', models.TextField(blank=True, null=True)),
                ('required', models.BooleanField(default=False)),
                ('default_value', models.TextField(blank=True, null=True)),
                ('help_text', models.TextField(blank=True, null=True)),
                ('choices', models.TextField(blank=True, null=True)),
                ('is_visible', models.BooleanField(default=True)),
                ('is_editable', models.BooleanField(default=True)),
                ('permission_required', models.CharField(blank=True, max_length=100, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('version', models.IntegerField(default=1)),
            ],
            options={
                'unique_together': {('entity_name', 'property_name')},
                'indexes': [
                    models.Index(fields=['entity_name', 'property_name']),
                    models.Index(fields=['entity_name', 'is_visible']),
                    models.Index(fields=['entity_name', 'is_editable']),
                ],
            },
        ),
        migrations.CreateModel(
            name='EntityMetadata',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('entity_name', models.CharField(max_length=100, unique=True)),
                ('label', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True, null=True)),
                ('icon', models.CharField(blank=True, max_length=50, null=True)),
                ('category', models.CharField(blank=True, max_length=50, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('version', models.IntegerField(default=1)),
            ],
        ),
    ] 