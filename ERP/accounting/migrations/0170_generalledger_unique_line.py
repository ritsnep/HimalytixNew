from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0169_add_auditlog_organization'),
    ]

    operations = [
        migrations.RenameField(
            model_name='generalledger',
            old_name='organization_id',
            new_name='organization',
        ),
        migrations.AlterField(
            model_name='generalledger',
            name='organization',
            field=models.ForeignKey(
                db_column='organization_id',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='general_ledgers',
                to='usermanagement.organization',
            ),
        ),
        migrations.AddConstraint(
            model_name='generalledger',
            constraint=models.UniqueConstraint(
                fields=('journal_line',),
                name='unique_gl_per_journal_line',
            ),
        ),
    ]
