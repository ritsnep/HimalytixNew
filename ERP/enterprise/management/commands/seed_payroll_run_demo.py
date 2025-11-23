from datetime import date
from decimal import Decimal
import csv
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone

from enterprise.models import (
    Employee,
    PayrollCycle,
    PayrollRun,
    PayrollRunLine,
    PayComponent,
)
from enterprise.services import PayrollService
from accounting.models import ChartOfAccount, JournalType
from usermanagement.models import Organization
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Seeds pay components, creates a payroll run with lines for all employees, posts it, and exports CSV."

    def add_arguments(self, parser):
        parser.add_argument("--org-code", required=True, help="Organization code")
        parser.add_argument("--username", required=True, help="Username to attribute the posting")
        parser.add_argument("--expense-account", required=True, help="Account code for payroll expense")
        parser.add_argument("--liability-account", required=True, help="Account code for payroll liability/payable")
        parser.add_argument("--earning-code", default="BASIC", help="Earning component code")
        parser.add_argument("--deduction-code", default="TAX", help="Deduction component code")
        parser.add_argument("--deduction-rate", type=float, default=0.1, help="Deduction rate (e.g., 0.1 for 10%)")
        parser.add_argument("--base-amount", type=float, default=50000, help="Base earning per employee")
        parser.add_argument("--journal-type", default="PAY", help="JournalType code or name to use when posting")
        parser.add_argument(
            "--export-dir",
            default=".",
            help="Directory to write payroll export CSV",
        )

    def handle(self, *args, **options):
        org_code = options["org_code"]
        username = options["username"]
        earning_code = options["earning_code"]
        deduction_code = options["deduction_code"]
        deduction_rate = Decimal(str(options["deduction_rate"]))
        base_amount = Decimal(str(options["base_amount"]))
        export_dir = Path(options["export_dir"])

        try:
            org = Organization.objects.get(code=org_code)
        except Organization.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Organization {org_code} not found"))
            return

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"User {username} not found"))
            return

        def get_account(code):
            try:
                return ChartOfAccount.objects.get(organization=org, account_code=code)
            except ChartOfAccount.DoesNotExist:
                raise ValueError(f"Account {code} not found for org {org_code}")

        try:
            expense_account = get_account(options["expense_account"])
            liability_account = get_account(options["liability_account"])
        except ValueError as exc:
            self.stderr.write(self.style.ERROR(str(exc)))
            return

        jt = (
            JournalType.objects.filter(organization=org, code=options["journal_type"])
            | JournalType.objects.filter(organization=org, name=options["journal_type"])
        ).first()
        if not jt:
            self.stderr.write(
                self.style.ERROR(
                    f"JournalType {options['journal_type']} not found for org {org_code}"
                )
            )
            return

        today = date.today()
        period_start = date(today.year, today.month, 1)
        period_end = date(today.year, today.month, 28)  # safe placeholder; not used for period lookup

        cycle, _ = PayrollCycle.objects.get_or_create(
            organization=org,
            name=f"Payroll {today:%Y-%m}",
            defaults={
                "period_start": period_start,
                "period_end": period_end,
                "status": PayrollCycle.PayrollStatus.APPROVED,
            },
        )

        earning_component, _ = PayComponent.objects.get_or_create(
            organization=org,
            code=earning_code,
            defaults={
                "name": "Basic Pay",
                "component_type": PayComponent.ComponentType.EARNING,
                "amount_type": PayComponent.AmountType.FIXED,
                "amount_value": base_amount,
                "account": expense_account,
                "is_taxable": True,
                "is_active": True,
            },
        )
        deduction_component, _ = PayComponent.objects.get_or_create(
            organization=org,
            code=deduction_code,
            defaults={
                "name": "Tax Withholding",
                "component_type": PayComponent.ComponentType.DEDUCTION,
                "amount_type": PayComponent.AmountType.PERCENT,
                "amount_value": deduction_rate * Decimal("100"),  # store as percent-of-base
                "account": liability_account,
                "is_taxable": False,
                "is_active": True,
            },
        )

        run = PayrollRun.objects.create(
            organization=org,
            payroll_cycle=cycle,
            period_start=period_start,
            period_end=period_end,
            status=PayrollRun.RunStatus.DRAFT,
            expense_account=expense_account,
            liability_account=liability_account,
        )

        employees = list(Employee.objects.filter(organization=org))
        if not employees:
            self.stderr.write(self.style.WARNING("No employees found; payroll run created without lines."))
            return

        lines_created = 0
        for emp in employees:
            PayrollRunLine.objects.create(
                organization=org,
                payroll_run=run,
                employee=emp,
                component=earning_component,
                amount=base_amount,
                notes="Seeded earning",
            )
            lines_created += 1
            deduction_amount = (base_amount * deduction_rate).quantize(Decimal("0.01"))
            if deduction_amount > 0:
                PayrollRunLine.objects.create(
                    organization=org,
                    payroll_run=run,
                    employee=emp,
                    component=deduction_component,
                    amount=deduction_amount,
                    notes="Seeded deduction",
                )
                lines_created += 1

        service = PayrollService(user, org)
        service.post_run(run)

        # Export CSV
        export_path = export_dir / f"payroll_run_{run.pk}.csv"
        export_dir.mkdir(parents=True, exist_ok=True)
        service.generate_entries(run)
        with export_path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Employee", "Gross", "Deductions", "Net", "Currency", "Run"])
            for entry in run.entries.select_related("employee"):
                writer.writerow(
                    [
                        str(entry.employee),
                        entry.gross_pay,
                        entry.deductions,
                        entry.net_pay,
                        entry.currency,
                        run.period_end,
                    ]
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Created payroll run {run.pk}, lines={lines_created}, posted journal, exported to {export_path}"
            )
        )
