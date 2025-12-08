from pathlib import Path

from django.conf import settings
from django.db import migrations


def seed_journal_report(apps, schema_editor):
    ReportDefinition = apps.get_model("reporting", "ReportDefinition")
    ReportTemplate = apps.get_model("reporting", "ReportTemplate")

    definition, _ = ReportDefinition.objects.get_or_create(
        code="journal_report",
        organization=None,
        defaults={
            "name": "Journal Report",
            "description": "Detailed journal with lines and totals.",
            "base_template_name": "reporting/base/journal_report.html",
            "query_name": "fn_report_journal",
            "is_custom_enabled": True,
        },
    )

    template_path = Path(settings.BASE_DIR) / "reporting" / "templates" / "reporting" / "gallery" / "journal_modern.html"
    if template_path.exists():
        html = template_path.read_text(encoding="utf-8")
        ReportTemplate.objects.get_or_create(
            definition=definition,
            organization=None,
            name="Modern Journal",
            defaults={
                "description": "Sleek dark journal layout.",
                "template_html": html,
                "template_json": {},
                "engine": "django",
                "is_default": False,
                "is_gallery": True,
                "version": 1,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("reporting", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_journal_report, migrations.RunPython.noop),
    ]
