from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from usermanagement.models import Organization
from accounting.models import (
    FiscalYear,
    AccountingPeriod,
    AccountType,
    ChartOfAccount,
    Currency,
    JournalType,
    VoucherModeConfig,
)


class Command(BaseCommand):
    help = "Seed minimal data required to use the voucher wizard (idempotent)."

    def handle(self, *args, **options):
        User = get_user_model()
        self.stdout.write("Seeding minimal voucher demo data…")

        # 1) Ensure at least one organization exists
        org, _ = Organization.objects.get_or_create(
            name="Demo Org",
            defaults={
                "code": "DEMO-001",
                "type": "company",
                "base_currency_code": "USD",
                "is_active": True,
            },
        )

        # 2) Assign organization to first superuser if missing
        admin = User.objects.filter(is_superuser=True).first()
        if admin and not getattr(admin, "organization", None):
            admin.organization = org
            admin.save(update_fields=["organization"])
            self.stdout.write(self.style.SUCCESS(f"Assigned admin '{admin.username}' to organization '{org.name}'."))

        # 3) Ensure default currency
        Currency.objects.get_or_create(
            currency_code=org.base_currency_code or "USD",
            defaults={"currency_name": "US Dollar", "symbol": "$"},
        )

        # 4) Ensure fiscal year and an open accounting period covering today
        today = timezone.now().date()
        fy, _ = FiscalYear.objects.get_or_create(
            organization=org,
            code=f"FY{today.year}",
            defaults={
                "name": f"Fiscal Year {today.year}",
                "start_date": today.replace(month=1, day=1),
                "end_date": today.replace(month=12, day=31),
                "is_current": True,
            },
        )
        AccountingPeriod.objects.get_or_create(
            fiscal_year=fy,
            period_number=today.month,
            name=f"{today.year}-{today.month:02d}",
            defaults={
                "start_date": today.replace(day=1),
                "end_date": (today.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1),
                "status": "open",
            },
        )

        # 5) Ensure basic account types
        at_map = {}
        for name, nature in (
            ("Asset", "asset"),
            ("Liability", "liability"),
            ("Equity", "equity"),
            ("Income", "income"),
            ("Expense", "expense"),
        ):
            at, _ = AccountType.objects.get_or_create(
                name=name,
                defaults={"nature": nature, "classification": name.lower(), "display_order": 1},
            )
            at_map[nature] = at

        # 6) Ensure a couple of accounts for demo
        cash, _ = ChartOfAccount.objects.get_or_create(
            organization=org,
            account_code="1010",
            defaults={
                "account_name": "Cash",
                "account_type": at_map["asset"],
                "allow_manual_journal": True,
            },
        )
        expense, _ = ChartOfAccount.objects.get_or_create(
            organization=org,
            account_code="5010",
            defaults={
                "account_name": "Office Supplies Expense",
                "account_type": at_map["expense"],
                "allow_manual_journal": True,
            },
        )

        # 7) Ensure at least one journal type for the org
        jt, _ = JournalType.objects.get_or_create(
            organization=org,
            code="GJ",
            defaults={"name": "General Journal", "sequence_next": 1},
        )

        # 8) Ensure a default voucher mode config with a minimal UI schema
        default_ui_schema = {
            "header": {
                "journal_date": {"type": "date", "label": "Date", "required": True},
                "description": {"type": "char", "label": "Description", "required": False},
            },
            "lines": {
                "account": {"type": "account", "label": "Account", "required": True},
                "debit_amount": {"type": "decimal", "label": "Debit", "required": False},
                "credit_amount": {"type": "decimal", "label": "Credit", "required": False},
            },
        }
        VoucherModeConfig.objects.get_or_create(
            organization=org,
            code="VM001",
            defaults={
                "name": "Standard Voucher",
                "is_default": True,
                "is_active": True,
                "journal_type": jt,
                "ui_schema": default_ui_schema,
            },
        )

        self.stdout.write(self.style.SUCCESS("Minimal voucher demo data ensured."))
