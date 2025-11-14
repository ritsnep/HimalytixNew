from __future__ import annotations

import csv
from pathlib import Path

from django.core.management.base import BaseCommand

from accounting.models import ApprovalTask, Organization, TaxLiability


class Command(BaseCommand):
    help = "Export compliance datasets for tax liabilities and approvals."

    def add_arguments(self, parser):
        parser.add_argument(
            "--org-code",
            required=True,
            help="Organization code to export data for.",
        )
        parser.add_argument(
            "--out-dir",
            default=".",
            help="Directory where CSV files will be written.",
        )

    def handle(self, *args, **options):
        org_code = options["org_code"]
        out_dir = Path(options["out_dir"])
        out_dir.mkdir(parents=True, exist_ok=True)

        org = Organization.objects.get(code=org_code)
        self._export_tax_liabilities(org, out_dir / "tax_liabilities.csv")
        self._export_approvals(org, out_dir / "approval_tasks.csv")

    def _export_tax_liabilities(self, org: Organization, path: Path):
        headers = ["tax_code", "period_start", "period_end", "amount", "status"]
        rows = TaxLiability.objects.filter(organization=org).values_list(
            "tax_code__code",
            "period_start",
            "period_end",
            "amount",
            "status",
        )
        with path.open("w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)
            writer.writerows(rows)
        self.stdout.write(f"Tax liabilities exported to {path}")

    def _export_approvals(self, org: Organization, path: Path):
        headers = ["workflow", "content_object", "status", "current_step", "notes", "updated_at"]
        rows = ApprovalTask.objects.filter(workflow__organization=org).values_list(
            "workflow__name",
            "content_object",
            "status",
            "current_step",
            "notes",
            "updated_at",
        )
        with path.open("w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)
            writer.writerows(rows)
        self.stdout.write(f"Approval tasks exported to {path}")
