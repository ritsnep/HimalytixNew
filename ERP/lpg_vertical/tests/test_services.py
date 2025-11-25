from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.test import TestCase

from accounting.models import AccountingPeriod, AccountType, ChartOfAccount, FiscalYear
from lpg_vertical.models import (
    ConversionRule,
    CylinderSKU,
    CylinderType,
    Dealer,
    LpgProduct,
    NocPurchase,
    SalesInvoice,
    SalesInvoiceLine,
)
from lpg_vertical.services import allocate_lpg_to_cylinders, get_company_config, post_noc_purchase, post_sales_invoice
from usermanagement.models import Organization


class LPGServiceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name="Test Co",
            code="TEST",
            type="company",
            vertical_type="depot",
            base_currency_code="NPR",
        )
        fy = FiscalYear.objects.create(
            organization=self.org,
            code="FY24",
            name="FY24",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            is_current=True,
        )
        AccountingPeriod.objects.create(
            fiscal_year=fy,
            organization=self.org,
            period_number=1,
            name="Jan",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            status="open",
        )

        # Minimal COA setup
        self.asset_type = AccountType.objects.create(
            code="AST",
            name="Assets",
            nature="asset",
            classification="BS",
            balance_sheet_category="Assets",
            income_statement_category="",
            cash_flow_category="Operating Activities",
            display_order=1,
        )
        self.liability_type = AccountType.objects.create(
            code="LIA",
            name="Liabilities",
            nature="liability",
            classification="BS",
            balance_sheet_category="Liabilities",
            income_statement_category="",
            cash_flow_category="Financing Activities",
            display_order=2,
        )
        self.income_type = AccountType.objects.create(
            code="INC",
            name="Income",
            nature="income",
            classification="PL",
            balance_sheet_category="",
            income_statement_category="Revenue",
            cash_flow_category="Operating Activities",
            display_order=3,
        )
        self.expense_type = AccountType.objects.create(
            code="EXP",
            name="Expense",
            nature="expense",
            classification="PL",
            balance_sheet_category="",
            income_statement_category="Expense",
            cash_flow_category="Operating Activities",
            display_order=4,
        )

        self.inventory_account = ChartOfAccount.objects.create(
            organization=self.org,
            account_type=self.asset_type,
            account_code="1000",
            account_name="Inventory",
        )
        self.cash_account = ChartOfAccount.objects.create(
            organization=self.org,
            account_type=self.asset_type,
            account_code="1010",
            account_name="Bank",
            is_bank_account=True,
        )
        self.ap_account = ChartOfAccount.objects.create(
            organization=self.org,
            account_type=self.liability_type,
            account_code="2000",
            account_name="Accounts Payable",
        )
        self.ar_account = ChartOfAccount.objects.create(
            organization=self.org,
            account_type=self.asset_type,
            account_code="1100",
            account_name="Accounts Receivable",
        )
        self.revenue_account = ChartOfAccount.objects.create(
            organization=self.org,
            account_type=self.income_type,
            account_code="4000",
            account_name="Sales Revenue",
        )
        self.expense_account = ChartOfAccount.objects.create(
            organization=self.org,
            account_type=self.expense_type,
            account_code="5000",
            account_name="Freight Expense",
        )

        # Ensure company config toggles are on
        config = get_company_config(self.org)
        config.enable_noc_purchases = True
        config.enable_dealer_management = True
        config.enable_logistics = True
        config.save()

    def test_allocate_lpg_to_cylinders(self):
        cyl_type = CylinderType.objects.create(
            organization=self.org,
            name="14.2 KG",
            kg_per_cylinder=Decimal("14.2"),
        )
        sku = CylinderSKU.objects.create(
            organization=self.org,
            name="14.2 KG Filled",
            cylinder_type=cyl_type,
            state=CylinderSKU.STATE_FILLED,
            code="142F",
        )
        ConversionRule.objects.create(
            organization=self.org,
            cylinder_type=cyl_type,
            mt_fraction_per_cylinder=Decimal("0.0142"),
            is_default=True,
        )
        purchase = NocPurchase.objects.create(
            organization=self.org,
            bill_no="B001",
            date=date(2024, 1, 5),
            quantity_mt=Decimal("1.000"),
            rate_per_mt=Decimal("1000"),
        )
        allocations = allocate_lpg_to_cylinders(purchase)
        assert allocations[sku] == 70

    def test_post_noc_purchase_posts_journal_and_movement(self):
        cyl_type = CylinderType.objects.create(
            organization=self.org,
            name="14.2 KG",
            kg_per_cylinder=Decimal("14.2"),
        )
        CylinderSKU.objects.create(
            organization=self.org,
            name="14.2 KG Filled",
            cylinder_type=cyl_type,
            state=CylinderSKU.STATE_FILLED,
            code="142F",
        )
        ConversionRule.objects.create(
            organization=self.org,
            cylinder_type=cyl_type,
            mt_fraction_per_cylinder=Decimal("0.0142"),
            is_default=True,
        )
        purchase = NocPurchase.objects.create(
            organization=self.org,
            bill_no="B002",
            date=date(2024, 1, 10),
            quantity_mt=Decimal("1.000"),
            rate_per_mt=Decimal("1000"),
            transport_cost=Decimal("50"),
            tax_amount=Decimal("13"),
        )

        post_noc_purchase(purchase)
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, NocPurchase.STATUS_POSTED)
        self.assertIsNotNone(purchase.posted_journal)
        self.assertGreater(InventoryMovement.objects.filter(ref_doc_id=purchase.id).count(), 0)

    def test_post_sales_invoice_blocks_credit(self):
        dealer = Dealer.objects.create(
            organization=self.org,
            company_code="D01",
            name="Dealer One",
            credit_limit=Decimal("100"),
        )
        sku = CylinderSKU.objects.create(
            organization=self.org,
            name="14.2 KG Filled",
            cylinder_type=CylinderType.objects.create(
                organization=self.org, name="14.2 KG", kg_per_cylinder=Decimal("14.2")
            ),
            state=CylinderSKU.STATE_FILLED,
            code="142F-2",
        )
        product = LpgProduct.objects.create(organization=self.org, code="LPG", name="Bulk LPG")
        invoice = SalesInvoice.objects.create(
            organization=self.org,
            invoice_no="INV-1",
            dealer=dealer,
            payment_type="credit",
            date=date(2024, 1, 15),
        )
        SalesInvoiceLine.objects.create(
            organization=self.org,
            invoice=invoice,
            product=product,
            cylinder_sku=sku,
            quantity=Decimal("10"),
            rate=Decimal("15"),
            discount=Decimal("0"),
            tax_rate=Decimal("0"),
        )
        invoice.recompute_totals()
        invoice.save()

        with pytest.raises(ValidationError):
            post_sales_invoice(invoice)
