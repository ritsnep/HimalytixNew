from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounting.models import (
    AccountingPeriod,
    AccountType,
    ChartOfAccount,
    Currency,
    FiscalYear,
    JournalLine,
    JournalType,
    LandedCostBasis,
    LandedCostDocument,
    LandedCostLine,
    PaymentTerm,
    Vendor,
)
from accounting.services.landed_cost_service import LandedCostService
from accounting.services.purchase_invoice_service import PurchaseInvoiceService
from inventory.models import InventoryItem, Product, Warehouse
from usermanagement.models import CustomUser, Organization


class LandedCostServiceTests(TestCase):
    def setUp(self) -> None:
        self.organization = Organization.objects.create(name="LC Org", code="LCORG", type="company")
        self.currency = Currency.objects.create(currency_code="USD", currency_name="US Dollar", symbol="$")

        self.asset_type = AccountType.objects.create(
            code="AST",
            name="Asset",
            nature="asset",
            classification="balance",
            display_order=1,
        )
        self.liability_type = AccountType.objects.create(
            code="LIA",
            name="Liability",
            nature="liability",
            classification="balance",
            display_order=2,
        )
        self.expense_type = AccountType.objects.create(
            code="EXP",
            name="Expense",
            nature="expense",
            classification="income",
            display_order=4,
        )

        self.inventory_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=self.asset_type,
            account_code="1300",
            account_name="Inventory",
            currency=self.currency,
        )
        self.grir_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=self.liability_type,
            account_code="2150",
            account_name="GRIR",
            currency=self.currency,
        )
        self.ap_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=self.liability_type,
            account_code="2100",
            account_name="Accounts Payable",
            currency=self.currency,
        )
        self.freight_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=self.expense_type,
            account_code="5200",
            account_name="Freight Expense",
            currency=self.currency,
        )

        fiscal_year = FiscalYear.objects.create(
            organization=self.organization,
            code="FY25",
            name="Fiscal 2025",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            status="open",
            is_current=True,
        )
        AccountingPeriod.objects.create(
            organization=self.organization,
            fiscal_year=fiscal_year,
            name="Jan 2025",
            period_number=1,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            status="open",
            is_current=True,
        )

        self.vendor_term = PaymentTerm.objects.create(
            organization=self.organization,
            code="AP30",
            name="Net 30",
            term_type="ap",
            net_due_days=30,
        )
        self.vendor = Vendor.objects.create(
            organization=self.organization,
            code="VEND1",
            display_name="Landed Cost Vendor",
            accounts_payable_account=self.ap_account,
            payment_term=self.vendor_term,
            default_currency=self.currency,
        )

        self.user = CustomUser.objects.create_user(
            username="landed_user",
            password="pass",
            organization=self.organization,
            full_name="Landed Cost User",
        )
        self.user.role = "superadmin"
        self.user.is_superuser = True
        self.user.is_staff = True
        self.user.save(update_fields=["role", "is_superuser", "is_staff"])

        self.purchase_journal_type = JournalType.objects.create(
            organization=self.organization,
            code="PI",
            name="Purchase",
            auto_numbering_prefix="PI",
        )

        self.warehouse = Warehouse.objects.create(
            organization=self.organization,
            code="WH1",
            name="Primary Warehouse",
            address_line1="123 Storage Way",
            city="Kathmandu",
            country_code="NP",
            inventory_account=self.inventory_account,
        )

        self.product = Product.objects.create(
            organization=self.organization,
            code="INV-001",
            name="Inventory Item",
            is_inventory_item=True,
            inventory_account=self.inventory_account,
            expense_account=self.freight_account,
            sale_price=Decimal("100"),
            cost_price=Decimal("20"),
        )

        self.purchase_service = PurchaseInvoiceService(self.user)
        self.landed_cost_service = LandedCostService(self.user)

    def _post_purchase_invoice(self, quantity: Decimal, unit_cost: Decimal, *, exchange_rate=Decimal("1")):
        invoice = self.purchase_service.create_invoice(
            organization=self.organization,
            vendor=self.vendor,
            invoice_number="PI-1",
            invoice_date=date(2025, 1, 10),
            currency=self.currency,
            exchange_rate=exchange_rate,
            lines=[
                {
                    "description": "Inventory receipt",
                    "account": self.inventory_account,
                    "product_code": self.product.code,
                    "quantity": quantity,
                    "unit_cost": unit_cost,
                }
            ],
        )
        self.purchase_service.validate_invoice(invoice)
        self.purchase_service.post_invoice(
            invoice,
            self.purchase_journal_type,
            use_grir=True,
            warehouse=self.warehouse,
            grir_account=self.grir_account,
        )
        return invoice

    def test_apply_landed_cost_updates_inventory_and_posts_journal(self):
        invoice = self._post_purchase_invoice(Decimal("3"), Decimal("50"))
        document = LandedCostDocument.objects.create(
            organization=self.organization,
            purchase_invoice=invoice,
            document_date=date(2025, 1, 12),
            currency=self.currency,
            exchange_rate=Decimal("1.00"),
            basis=LandedCostBasis.BY_VALUE,
        )
        LandedCostLine.objects.create(
            document=document,
            description="Freight",
            amount=Decimal("30"),
            credit_account=self.freight_account,
        )

        self.landed_cost_service.apply(document, journal_type=self.purchase_journal_type)
        document.refresh_from_db()

        self.assertTrue(document.is_applied)
        self.assertIsNotNone(document.journal)
        allocation = document.allocations.get()
        self.assertEqual(allocation.amount, Decimal("30.0000"))

        item = InventoryItem.objects.get(
            organization=self.organization,
            product=self.product,
            warehouse=self.warehouse,
        )
        self.assertEqual(item.quantity_on_hand, Decimal("3"))
        self.assertEqual(item.unit_cost, Decimal("60.0000"))

        lines = JournalLine.objects.filter(journal=document.journal)
        self.assertTrue(lines.filter(account=self.inventory_account, debit_amount=Decimal("30")).exists())
        self.assertTrue(lines.filter(account=self.freight_account, credit_amount=Decimal("30")).exists())

    def test_apply_uses_invoice_exchange_rate_when_missing(self):
        invoice = self._post_purchase_invoice(Decimal("1"), Decimal("100"), exchange_rate=Decimal("1.50"))
        document = LandedCostDocument.objects.create(
            organization=self.organization,
            purchase_invoice=invoice,
            document_date=date(2025, 1, 12),
            currency=self.currency,
            exchange_rate=Decimal("0"),  # force fallback
            basis=LandedCostBasis.BY_QUANTITY,
        )
        LandedCostLine.objects.create(
            document=document,
            description="Duty",
            amount=Decimal("15"),
            credit_account=self.freight_account,
        )

        journal = self.landed_cost_service.apply(document, journal_type=self.purchase_journal_type)
        document.refresh_from_db()
        self.assertEqual(journal.exchange_rate, invoice.exchange_rate)
        self.assertEqual(document.exchange_rate, invoice.exchange_rate)

    def test_apply_requires_posted_invoice(self):
        invoice = self.purchase_service.create_invoice(
            organization=self.organization,
            vendor=self.vendor,
            invoice_number="PI-UNPOSTED",
            invoice_date=date(2025, 1, 15),
            currency=self.currency,
            lines=[
                {
                    "description": "Inventory receipt",
                    "account": self.inventory_account,
                    "product_code": self.product.code,
                    "quantity": Decimal("1"),
                    "unit_cost": Decimal("40"),
                }
            ],
        )
        self.purchase_service.validate_invoice(invoice)
        document = LandedCostDocument.objects.create(
            organization=self.organization,
            purchase_invoice=invoice,
            document_date=date(2025, 1, 12),
            currency=self.currency,
            exchange_rate=Decimal("1"),
            basis=LandedCostBasis.BY_VALUE,
        )
        LandedCostLine.objects.create(
            document=document,
            description="Freight",
            amount=Decimal("10"),
            credit_account=self.freight_account,
        )

        with self.assertRaises(ValidationError):
            self.landed_cost_service.apply(document, journal_type=self.purchase_journal_type)
