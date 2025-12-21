from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone
from usermanagement.models import Organization
from accounting.models import (
    AccountingPeriod,
    AccountType,
    ChartOfAccount,
    Currency,
    FiscalYear,
    JournalType,
    TransactionTypeConfig,
    VoucherModeConfig,
)
from accounting.voucher_schema import ui_schema_to_definition


def build_item_schema(party_key, party_label, extra_header=None):
    header = {
        "journal_date": {"type": "date", "label": "Date", "required": True},
        "reference_number": {"type": "char", "label": "Reference", "required": False},
        party_key: {"type": "char", "label": party_label, "required": True},
        "currency": {"type": "char", "label": "Currency", "required": True},
        "description": {"type": "char", "label": "Description", "required": False},
    }
    if extra_header:
        header.update(extra_header)
    lines = {
        "item": {"type": "char", "label": "Item/Service", "required": True},
        "description": {"type": "char", "label": "Description", "required": False},
        "quantity": {"type": "decimal", "label": "Quantity", "required": True, "default": 1},
        "unit_price": {"type": "decimal", "label": "Unit Price", "required": True},
        "discount_percent": {"type": "decimal", "label": "Discount %", "required": False, "default": 0},
        "tax_percent": {"type": "decimal", "label": "Tax %", "required": False, "default": 13},
        "warehouse": {"type": "char", "label": "Warehouse / Location", "required": False},
        "batch": {"type": "char", "label": "Batch / Lot", "required": False},
        "line_total": {"type": "decimal", "label": "Line Total", "required": False},
    }
    return {"header": header, "lines": lines}


class Command(BaseCommand):
    help = "Seed minimal data required to use the voucher wizard (idempotent)."

    def handle(self, *args, **options):
        User = get_user_model()
        self.stdout.write("Seeding minimal voucher demo data…")

        # 1) Ensure default currency exists first (needed for Organization FK)
        default_currency, _ = Currency.objects.get_or_create(
            currency_code="USD",
            defaults={"currency_name": "US Dollar", "symbol": "$"},
        )

        # 2) Ensure at least one organization exists
        org, _ = Organization.objects.get_or_create(
            name="Demo Org",
            defaults={
                "code": "DEMO-001",
                "type": "company",
                "base_currency_code": default_currency,
                "is_active": True,
            },
        )

        # 3) Assign organization to first superuser if missing
        admin = User.objects.filter(is_superuser=True).first()
        if admin and not getattr(admin, "organization", None):
            admin.organization = org
            admin.save(update_fields=["organization"])
            self.stdout.write(self.style.SUCCESS(f"Assigned admin '{admin.username}' to organization '{org.name}'."))

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

        # Schema builders reused below
        journal_ui_schema = {
            "header": {
                "journal_date": {"type": "date", "label": "Date", "required": True},
                "reference_number": {"type": "char", "label": "Reference", "required": False},
                "description": {"type": "char", "label": "Narration", "required": False},
                "currency": {"type": "char", "label": "Currency", "required": True},
            },
            "lines": {
                "account": {"type": "char", "label": "Account", "required": True},
                "description": {"type": "char", "label": "Description", "required": False},
                "debit_amount": {"type": "decimal", "label": "Debit", "required": False},
                "credit_amount": {"type": "decimal", "label": "Credit", "required": False},
                "cost_center": {"type": "char", "label": "Cost Center", "required": False},
            },
        }

        purchase_item_schema = build_item_schema(
            "supplier",
            "Supplier",
            extra_header={
                "supplier_invoice_number": {"type": "char", "label": "Party Inv No.", "required": False},
                "invoice_date_bs": {"type": "bsdate", "label": "Date (BS)", "required": False},
                "payment_mode": {
                    "type": "select",
                    "label": "Payment Mode",
                    "choices": [
                        ("cash", "Cash"),
                        ("credit", "Credit"),
                        ("cheque", "Cheque"),
                        ("bank_transfer", "Bank Transfer"),
                    ],
                    "default": "credit",
                },
                "agent": {"type": "agent", "label": "Agent", "required": False},
                "agent_area": {"type": "char", "label": "Agent Area", "required": False},
                "purchase_account": {"type": "account", "label": "Purchase Account", "required": False},
                "discount_amount": {"type": "decimal", "label": "Discount", "required": False, "default": 0},
                "rounding_adjustment": {"type": "decimal", "label": "Rounding", "required": False, "default": 0},
                "narration": {"type": "text", "label": "Narration", "required": False},
            },
        )
        # Remove default description from header since we have narration
        if "description" in purchase_item_schema["header"]:
            del purchase_item_schema["header"]["description"]
        
        # Add additional_charges section for Purchase Invoice
        purchase_item_schema["additional_charges"] = {
            "description": {"type": "char", "label": "Description", "required": True},
            "amount": {"type": "decimal", "label": "Amount", "required": True},
            "gl_account": {"type": "account", "label": "GL Account", "required": True},
            "is_taxable": {"type": "boolean", "label": "Taxable?", "required": False, "default": False},
        }

        goods_receipt_schema = build_item_schema(
            "vendor_name",
            "Vendor",
            extra_header={
                "receipt_number": {"type": "char", "label": "Receipt Number", "required": False},
                "warehouse_code": {"type": "char", "label": "Warehouse", "required": False},
            },
        )
        landed_cost_schema = build_item_schema(
            "vendor_name",
            "Vendor",
            extra_header={"cost_sheet_number": {"type": "char", "label": "Cost Sheet #", "required": False}},
        )
        landed_cost_schema["lines"]["cost_component"] = {"type": "char", "label": "Cost Component", "required": False}

        sales_item_schema = build_item_schema(
            "customer_name",
            "Customer",
            extra_header={
                "due_date": {"type": "date", "label": "Due Date", "required": False},
            },
        )
        sales_delivery_schema = build_item_schema(
            "customer_name",
            "Customer",
            extra_header={
                "delivery_date": {"type": "date", "label": "Delivery Date", "required": False},
                "delivery_note": {"type": "char", "label": "Delivery Note #", "required": False},
            },
        )

        voucher_blueprints = [
            {
                "config_code": "VM-JE",
                "name": "Journal Entry",
                "journal_type_code": "JE",
                "journal_type_name": "Journal Entry",
                "schema_definition": ui_schema_to_definition(journal_ui_schema),
                "is_default": True,
            },
            {"config_code": "VM-PO", "name": "Purchase Order", "journal_type_code": "PO", "journal_type_name": "Purchase Order", "schema_definition": ui_schema_to_definition(purchase_item_schema)},
            {"config_code": "VM-GR", "name": "Goods Receipt", "journal_type_code": "GR", "journal_type_name": "Goods Receipt", "schema_definition": ui_schema_to_definition(goods_receipt_schema)},
            {"config_code": "VM-PI", "name": "Purchase Invoice", "journal_type_code": "PI", "journal_type_name": "Purchase Invoice", "schema_definition": ui_schema_to_definition(purchase_item_schema)},
            {"config_code": "VM-PR", "name": "Purchase Return", "journal_type_code": "PR", "journal_type_name": "Purchase Return", "schema_definition": ui_schema_to_definition(purchase_item_schema)},
            {"config_code": "VM-PDN", "name": "Purchase Debit Note", "journal_type_code": "PDN", "journal_type_name": "Purchase Debit Note", "schema_definition": ui_schema_to_definition(purchase_item_schema)},
            {"config_code": "VM-PCN", "name": "Purchase Credit Note", "journal_type_code": "PCN", "journal_type_name": "Purchase Credit Note", "schema_definition": ui_schema_to_definition(purchase_item_schema)},
            {"config_code": "VM-LC", "name": "Landed Cost", "journal_type_code": "LC", "journal_type_name": "Landed Cost", "schema_definition": ui_schema_to_definition(landed_cost_schema)},
            {"config_code": "VM-SQ", "name": "Sales Quote", "journal_type_code": "SQ", "journal_type_name": "Sales Quote", "schema_definition": ui_schema_to_definition(sales_item_schema)},
            {"config_code": "VM-SO", "name": "Sales Order", "journal_type_code": "SO", "journal_type_name": "Sales Order", "schema_definition": ui_schema_to_definition(sales_item_schema)},
            {"config_code": "VM-SD", "name": "Sales Delivery", "journal_type_code": "SD", "journal_type_name": "Sales Delivery", "schema_definition": ui_schema_to_definition(sales_delivery_schema)},
            {"config_code": "VM-SI", "name": "Sales Invoice", "journal_type_code": "SI", "journal_type_name": "Sales Invoice", "schema_definition": ui_schema_to_definition(sales_item_schema)},
            {"config_code": "VM-SR", "name": "Sales Return", "journal_type_code": "SR", "journal_type_name": "Sales Return", "schema_definition": ui_schema_to_definition(sales_item_schema)},
            {"config_code": "VM-SDN", "name": "Sales Debit Note", "journal_type_code": "SDN", "journal_type_name": "Sales Debit Note", "schema_definition": ui_schema_to_definition(sales_item_schema)},
            {"config_code": "VM-SCN", "name": "Sales Credit Note", "journal_type_code": "SCN", "journal_type_name": "Sales Credit Note", "schema_definition": ui_schema_to_definition(sales_item_schema)},
        ]

        org_currency_code = org.base_currency_code.currency_code if hasattr(org.base_currency_code, "currency_code") else (org.base_currency_code or "USD")

        voucher_config_map = {}
        for spec in voucher_blueprints:
            jt, _ = JournalType.objects.get_or_create(
                organization=org,
                code=spec["journal_type_code"],
                defaults={"name": spec["journal_type_name"], "sequence_next": 1},
            )
            config_defaults = {
                "name": spec["name"],
                "is_default": spec.get("is_default", False),
                "is_active": True,
                "journal_type": jt,
                "schema_definition": spec["schema_definition"],
                "default_currency": org_currency_code,
            }
            config, created = VoucherModeConfig.objects.get_or_create(
                organization=org,
                code=spec["config_code"],
                defaults=config_defaults,
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created voucher config '{spec['name']}' ({spec['config_code']})."))
            elif spec.get("is_default") and not config.is_default:
                config.is_default = True
                config.save(update_fields=["is_default"])
                self.stdout.write(self.style.WARNING(f"Marked '{spec['name']}' as default voucher config."))
            voucher_config_map[spec["config_code"]] = config

        self.stdout.write(self.style.SUCCESS("Minimal voucher demo data ensured."))

        self.stdout.write("Seeding unified transaction type configs...")
        # seed_transaction_type_configs(org, org_currency_code, voucher_config_map)
