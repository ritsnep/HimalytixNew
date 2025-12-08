from pathlib import Path

from django.conf import settings
from django.db import migrations


def seed_reports(apps, schema_editor):
    ReportDefinition = apps.get_model("reporting", "ReportDefinition")
    ReportTemplate = apps.get_model("reporting", "ReportTemplate")

    seeds = [
        ("general_ledger", "General Ledger", "reporting/base/general_ledger.html", "reporting/gallery/general_ledger_modern.html", "fn_report_general_ledger"),
        ("trial_balance", "Trial Balance", "reporting/base/trial_balance.html", "reporting/gallery/trial_balance_modern.html", "fn_report_trial_balance"),
        ("profit_loss", "Profit & Loss", "reporting/base/profit_loss.html", "reporting/gallery/profit_loss_modern.html", "fn_report_profit_loss"),
        ("balance_sheet", "Balance Sheet", "reporting/base/balance_sheet.html", "reporting/gallery/balance_sheet_modern.html", "fn_report_balance_sheet"),
    ]

    for code, name, base_template, gallery_template, query_name in seeds:
        definition, _ = ReportDefinition.objects.get_or_create(
            code=code,
            organization=None,
            defaults={
                "name": name,
                "description": name,
                "base_template_name": base_template,
                "query_name": query_name,
                "is_custom_enabled": True,
            },
        )
        gallery_path = Path(settings.BASE_DIR) / gallery_template
        if gallery_path.exists():
            html = gallery_path.read_text(encoding="utf-8")
            ReportTemplate.objects.get_or_create(
                definition=definition,
                organization=None,
                name=f"{name} Modern",
                defaults={
                    "description": f"Modern layout for {name}",
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
        ("reporting", "0002_seed_journal_report"),
    ]

    operations = [
        migrations.RunPython(seed_reports, migrations.RunPython.noop),
    ]
