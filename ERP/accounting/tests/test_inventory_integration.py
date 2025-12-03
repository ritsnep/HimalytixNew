from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounting.models import (
    AccountingPeriod,
    AccountType,
    ChartOfAccount,
    Currency,
    Customer,
    FiscalYear,
    JournalLine,
    JournalType,
    PaymentTerm,
    Vendor,
)
from accounting.services.inventory_posting_service import InventoryPostingService
from accounting.services.purchase_invoice_service import PurchaseInvoiceService
from accounting.services.sales_invoice_service import SalesInvoiceService
from inventory.models import InventoryItem, Product, Warehouse
from usermanagement.models import CustomUser, Organization


class InventoryIntegrationTests(TestCase):
    def setUp(self) -> None:
        self.organization = Organization.objects.create(name="Inventory Org", code="INVORG", type="company")
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
        self.revenue_type = AccountType.objects.create(
            code="REV",
            name="Revenue",
            nature="income",
            classification="income",
            display_order=3,
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
        self.cogs_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=self.expense_type,
            account_code="5100",
            account_name="COGS",
            currency=self.currency,
        )
        self.revenue_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=self.revenue_type,
            account_code="4100",
            account_name="Revenue",
            currency=self.currency,
        )
        self.ar_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=self.asset_type,
            account_code="1100",
            account_name="Accounts Receivable",
            currency=self.currency,
        )
        self.ap_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=self.liability_type,
            account_code="2100",
            account_name="Accounts Payable",
            currency=self.currency,
        )
        self.grir_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=self.liability_type,
            account_code="2150",
            account_name="GRIR",
            currency=self.currency,
        )

        today = date(2025, 1, 15)
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

        self.customer_term = PaymentTerm.objects.create(
            organization=self.organization,
            code="AR15",
            name="Net 15",
            term_type="ar",
            net_due_days=15,
        )
        self.vendor_term = PaymentTerm.objects.create(
            organization=self.organization,
            code="AP30",
            name="Net 30",
            term_type="ap",
            net_due_days=30,
        )

        self.customer = Customer.objects.create(
            organization=self.organization,
            code="CUST1",
            display_name="Inventory Customer",
            accounts_receivable_account=self.ar_account,
            revenue_account=self.revenue_account,
            payment_term=self.customer_term,
            default_currency=self.currency,
        )
        self.vendor = Vendor.objects.create(
            organization=self.organization,
            code="VEND1",
            display_name="Inventory Vendor",
            accounts_payable_account=self.ap_account,
            payment_term=self.vendor_term,
            default_currency=self.currency,
        )

        self.user = CustomUser.objects.create_user(
            username="inventory_user",
            password="pass",
            organization=self.organization,
            full_name="Inventory User",
        )
        # Grant elevated rights so PostingService permission checks pass in isolation.
        self.user.role = "superadmin"
        self.user.is_superuser = True
        self.user.is_staff = True
        self.user.save(update_fields=["role", "is_superuser", "is_staff"])
        self.sales_service = SalesInvoiceService(self.user)
        self.purchase_service = PurchaseInvoiceService(self.user)

        self.sales_journal_type = JournalType.objects.create(
            organization=self.organization,
            code="SI",
            name="Sales",
            auto_numbering_prefix="SI",
        )
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
            expense_account=self.cogs_account,
            sale_price=Decimal("100"),
            cost_price=Decimal("20"),
        )

    def _create_sales_invoice(self):
        invoice = self.sales_service.create_invoice(
            organization=self.organization,
            customer=self.customer,
            invoice_date=date(2025, 1, 20),
            currency=self.currency,
            lines=[
                {
                    "description": "Inventory sale",
                    "revenue_account": self.revenue_account,
                    "product_code": self.product.code,
                    "quantity": Decimal("1"),
                    "unit_price": Decimal("100"),
                }
            ],
        )
        self.sales_service.validate_invoice(invoice)
        return invoice

    def _create_purchase_invoice(self, quantity: Decimal, unit_cost: Decimal):
        invoice = self.purchase_service.create_invoice(
            organization=self.organization,
            vendor=self.vendor,
            invoice_date=date(2025, 1, 10),
            currency=self.currency,
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
        return invoice

    def test_sales_invoice_requires_warehouse_for_inventory(self) -> None:
        invoice = self._create_sales_invoice()
        with self.assertRaises(ValidationError) as exc:
            self.sales_service.post_invoice(invoice, self.sales_journal_type)
        self.assertIn("Warehouse is required", str(exc.exception))

    def test_sales_invoice_posts_cogs_and_inventory_lines(self) -> None:
        inventory_service = InventoryPostingService(organization=self.organization)
        inventory_service.record_receipt(
            product=self.product,
            warehouse=self.warehouse,
            quantity=Decimal("5"),
            unit_cost=Decimal("20"),
            grir_account=self.grir_account,
            reference_id="INIT",
        )

        invoice = self._create_sales_invoice()
        posted = self.sales_service.post_invoice(
            invoice,
            self.sales_journal_type,
            warehouse=self.warehouse,
        )
        lines = JournalLine.objects.filter(journal=posted)
        self.assertEqual(lines.count(), 4)

        revenue_line = lines.get(account=self.revenue_account)
        self.assertEqual(revenue_line.credit_amount, Decimal("100"))
        ar_line = lines.get(account=self.ar_account)
        self.assertEqual(ar_line.debit_amount, Decimal("100"))

        cogs_line = lines.get(account=self.cogs_account)
        inventory_line = lines.get(account=self.inventory_account)
        self.assertEqual(cogs_line.debit_amount, Decimal("20"))
        self.assertEqual(inventory_line.credit_amount, Decimal("20"))

    def test_purchase_invoice_requires_warehouse_when_use_grir(self) -> None:
        invoice = self._create_purchase_invoice(Decimal("2"), Decimal("50"))
        with self.assertRaises(ValidationError) as exc:
            self.purchase_service.post_invoice(
                invoice,
                self.purchase_journal_type,
                use_grir=True,
                grir_account=self.grir_account,
            )
        self.assertIn("Warehouse is required", str(exc.exception))

    def test_purchase_invoice_inventory_receipt_updates_stock(self) -> None:
        invoice = self._create_purchase_invoice(Decimal("3"), Decimal("50"))
        posted = self.purchase_service.post_invoice(
            invoice,
            self.purchase_journal_type,
            use_grir=True,
            warehouse=self.warehouse,
            grir_account=self.grir_account,
        )
        lines = JournalLine.objects.filter(journal=posted)
        self.assertEqual(lines.count(), 4)

        inventory_line = lines.get(account=self.inventory_account)
        self.assertEqual(inventory_line.debit_amount, Decimal("150"))
        grir_lines = lines.filter(account=self.grir_account)
        self.assertEqual(grir_lines.count(), 2)
        self.assertTrue(grir_lines.filter(debit_amount=Decimal("150")).exists())
        self.assertTrue(grir_lines.filter(credit_amount=Decimal("150")).exists())
        ap_line = lines.get(account=self.ap_account)
        self.assertEqual(ap_line.credit_amount, Decimal("150"))

        item = InventoryItem.objects.get(
            organization=self.organization,
            product=self.product,
            warehouse=self.warehouse,
        )
        self.assertEqual(item.quantity_on_hand, Decimal("3"))
        self.assertEqual(item.unit_cost, Decimal("50"))
