from django.db import migrations, models
from django.db.models import F
import django.db.models.deletion


def backfill_journal_snapshot(apps, schema_editor):
    VoucherProcess = apps.get_model("accounting", "VoucherProcess")
    VoucherProcess.objects.filter(journal_id_snapshot__isnull=True).update(
        journal_id_snapshot=F("journal_id")
    )


class Migration(migrations.Migration):
    dependencies = [
        ("accounting", "0187_add_voucher_process"),
    ]

    operations = [
        migrations.AddField(
            model_name="voucherprocess",
            name="journal_id_snapshot",
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="voucherprocess",
            name="journal",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="process_attempts",
                to="accounting.journal",
            ),
        ),
        migrations.RunPython(backfill_journal_snapshot, migrations.RunPython.noop),
        migrations.AddIndex(
            model_name="voucherprocess",
            index=models.Index(fields=["journal_id_snapshot", "status"], name="vproc_journal_snap_status_idx"),
        ),
    ]
