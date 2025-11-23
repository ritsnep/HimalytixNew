from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('usermanagement', '0001_initial'),
        ('accounting', '0135_alter_fiscalyear_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='AutoIncrementSequence',
            fields=[
                ('sequence_id', models.BigAutoField(primary_key=True, serialize=False)),
                ('model_label', models.CharField(max_length=255)),
                ('field_name', models.CharField(max_length=255)),
                ('next_value', models.BigIntegerField(default=1)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'organization',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='auto_increment_sequences',
                        to='usermanagement.organization',
                    ),
                ),
            ],
            options={
                'db_table': 'auto_increment_sequence',
            },
        ),
        migrations.AddIndex(
            model_name='autoincrementsequence',
            index=models.Index(fields=['organization', 'model_label', 'field_name'], name='auto_incre_organi_51bb9f_idx'),
        ),
        migrations.AddConstraint(
            model_name='autoincrementsequence',
            constraint=models.UniqueConstraint(
                fields=('organization', 'model_label', 'field_name'),
                name='unique_sequence_per_org_and_model_field',
            ),
        ),
        migrations.AddConstraint(
            model_name='autoincrementsequence',
            constraint=models.UniqueConstraint(
                condition=models.Q(('organization__isnull', True)),
                fields=('model_label', 'field_name'),
                name='unique_global_sequence_per_model_field',
            ),
        ),
    ]
