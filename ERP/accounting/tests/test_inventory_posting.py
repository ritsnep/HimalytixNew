from decimal import Decimal

from django.test import TestCase

from accounting.models import AccountType, ChartOfAccount
from accounting.services.inventory_posting_service import InventoryPostingService
from inventory.models import (
    CostingMethod,
    Product,
    Warehouse,
)
from usermanagement.models import Organization


class InventoryPostingCostingTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Costing Org", code="CST", type="company")
        self.asset_type = AccountType.objects.create(
            code="AST-10",
            name="Asset Type",
            nature=AccountType.Nature.ASSET,
            classification=AccountType.Classification.CURRENT,
            balance_sheet_category=AccountType.BalanceSheetCategory.ASSETS,
            income_statement_category=None,
            cash_flow_category=AccountType.CashFlowCategory.INVESTING,
            display_order=1,
        )
        self.expense_type = AccountType.objects.create(
            code="EXP-10",
            name="Expense Type",
            nature=AccountType.Nature.EXPENSE,
            classification=AccountType.Classification.OPERATING,
            balance_sheet_category=None,
            income_statement_category=AccountType.IncomeStatementCategory.EXPENSE,
            cash_flow_category=AccountType.CashFlowCategory.OPERATING,
            display_order=2,
        )
        self.liability_type = AccountType.objects.create(
            code="LIA-10",
            name="Liability Type",
            nature=AccountType.Nature.LIABILITY,
            classification=AccountType.Classification.CURRENT,
            balance_sheet_category=AccountType.BalanceSheetCategory.CURRENT_LIABILITIES,
            income_statement_category=None,
            cash_flow_category=AccountType.CashFlowCategory.FINANCING,
            display_order=3,
        )

        self.inventory_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=self.asset_type,
            account_code="1000",
            account_name="Inventory",
        )
        self.cogs_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=self.expense_type,
            account_code="5000",
            account_name="COGS",
        )
        self.grir_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=self.liability_type,
            account_code="2000",
            account_name="GR/IR",
        )

        self.warehouse = Warehouse.objects.create(
            organization=self.organization,
            code="MAIN",
            name="Main Warehouse",
            address_line1="123 Main",
            city="Kathmandu",
            country_code="NP",
        )
        self.product = Product.objects.create(
            organization=self.organization,
            code="PRD-01",
            name="Costed Item",
            inventory_account=self.inventory_account,
            expense_account=self.cogs_account,
            is_inventory_item=True,
        )

    def _create_service(self):
        return InventoryPostingService(organization=self.organization)

    def test_fifo_consumes_layers_in_fifo_order(self):
        self.product.costing_method = CostingMethod.FIFO
        self.product.save(update_fields=["costing_method"])

        service = self._create_service()
        service.record_receipt(
            product=self.product,
            warehouse=self.warehouse,
            quantity=Decimal("5"),
            unit_cost=Decimal("10"),
            grir_account=self.grir_account,
            reference_id="RC-1",
        )
        service.record_receipt(
            product=self.product,
            warehouse=self.warehouse,
            quantity=Decimal("5"),
            unit_cost=Decimal("20"),
            grir_account=self.grir_account,
            reference_id="RC-2",
        )
        result = service.record_issue(
            product=self.product,
            warehouse=self.warehouse,
            quantity=Decimal("3"),
            reference_id="ISSUE-1",
            cogs_account=self.cogs_account,
        )
        self.assertEqual(result.ledger_entry.unit_cost, Decimal("10"))
        self.assertEqual(result.total_cost, Decimal("30"))

    def test_lifo_consumes_layers_in_lifo_order(self):
        self.product.costing_method = CostingMethod.LIFO
        self.product.save(update_fields=["costing_method"])

        service = self._create_service()
        service.record_receipt(
            product=self.product,
            warehouse=self.warehouse,
            quantity=Decimal("3"),
            unit_cost=Decimal("10"),
            grir_account=self.grir_account,
            reference_id="RC-1",
        )
        service.record_receipt(
            product=self.product,
            warehouse=self.warehouse,
            quantity=Decimal("2"),
            unit_cost=Decimal("25"),
            grir_account=self.grir_account,
            reference_id="RC-2",
        )
        result = service.record_issue(
            product=self.product,
            warehouse=self.warehouse,
            quantity=Decimal("2"),
            reference_id="ISSUE-1",
            cogs_account=self.cogs_account,
        )
        self.assertEqual(result.ledger_entry.unit_cost, Decimal("25"))
        self.assertEqual(result.total_cost, Decimal("50"))

    def test_standard_costing_uses_standard_cost(self):
        self.product.costing_method = CostingMethod.STANDARD
        self.product.standard_cost = Decimal("15.00")
        self.product.save(update_fields=["costing_method", "standard_cost"])

        service = self._create_service()
        service.record_receipt(
            product=self.product,
            warehouse=self.warehouse,
            quantity=Decimal("2"),
            unit_cost=Decimal("10"),
            grir_account=self.grir_account,
            reference_id="RC-1",
        )
        result = service.record_issue(
            product=self.product,
            warehouse=self.warehouse,
            quantity=Decimal("2"),
            reference_id="ISSUE-STD",
            cogs_account=self.cogs_account,
        )
        self.assertEqual(result.ledger_entry.unit_cost, Decimal("15"))
        self.assertEqual(result.total_cost, Decimal("30"))
