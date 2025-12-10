from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.db import models
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import TemplateView

from accounting.models import (
    ChartOfAccount, Journal, JournalLine, ReportDefinition, 
    SalesInvoice, Customer, JournalType, SalesInvoiceLine
)
from inventory.models import InventoryItem, Product as InventoryProduct, Warehouse
from accounting.services.report_export_service import ReportExportService
from accounting.services.report_service import ReportService
from accounting.utils.udf import filterable_udfs, pivot_udfs, serialize_udf_definition
from usermanagement.mixins import UserOrganizationMixin

logger = logging.getLogger(__name__)

DATE_FMT = "%Y-%m-%d"

REPORT_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "id": "general_ledger",
        "name": _("General Ledger"),
        "description": _("View all transactions by account with running balances."),
        "url_name": "report_ledger",
        "icon": "fas fa-book-open",
    },
    {
        "id": "trial_balance",
        "name": _("Trial Balance"),
        "description": _("Verify debits and credits balance for all accounts."),
        "url_name": "report_trial_balance",
        "icon": "fas fa-balance-scale",
    },
    {
        "id": "profit_loss",
        "name": _("Profit & Loss Statement"),
        "description": _("Analyse revenues, expenses, and net income for a period."),
        "url_name": "report_pl",
        "icon": "fas fa-chart-line",
    },
    {
        "id": "balance_sheet",
        "name": _("Balance Sheet"),
        "description": _("Summarise assets, liabilities, and equity at a point in time."),
        "url_name": "report_bs",
        "icon": "fas fa-landmark",
    },
    {
        "id": "cash_flow",
        "name": _("Cash Flow Statement"),
        "description": _("Track cash inflows and outflows by activity."),
        "url_name": "report_cf",
        "icon": "fas fa-water",
    },
    {
        "id": "ar_aging",
        "name": _("Accounts Receivable Aging"),
        "description": _("Bucket outstanding receivables by age."),
        "url_name": "report_ar_aging",
        "icon": "fas fa-user-clock",
    },
    {
        "id": "ap_aging",
        "name": _("Accounts Payable Aging"),
        "description": _("Review vendor balances by due date bucket."),
        "url_name": "report_ap_aging",
        "icon": "fas fa-file-invoice-dollar",
    },
    {
        "id": "sales_summary",
        "name": _("Sales Summary"),
        "description": _("Sales by period, product, customer, and top-selling items."),
        "url_name": "report_sales_summary",
        "icon": "fas fa-shopping-cart",
    },
    {
        "id": "inventory_summary",
        "name": _("Inventory Summary"),
        "description": _("Current stock levels, slow/fast-moving items, and valuation."),
        "url_name": "report_inventory_summary",
        "icon": "fas fa-boxes",
    },
    {
        "id": "tax_summary",
        "name": _("Tax Summary"),
        "description": _("VAT/GST summary for filing and tax reporting."),
        "url_name": "report_tax_summary",
        "icon": "fas fa-calculator",
    },
    {
        "id": "expense_summary",
        "name": _("Expense Summary"),
        "description": _("Expenditures by category over time."),
        "url_name": "report_expense_summary",
        "icon": "fas fa-receipt",
    },
]


def build_report_cards(namespace: str = "accounting") -> List[Dict[str, Any]]:
    """Return report metadata with resolved URLs for the requested namespace."""

    cards: List[Dict[str, Any]] = []
    for report in REPORT_DEFINITIONS:
        try:
            url = reverse(f"{namespace}:{report['url_name']}")
        except NoReverseMatch:
            url = reverse(f"accounting:{report['url_name']}")
        cards.append(
            {
                "id": report["id"],
                "name": report["name"],
                "description": report["description"],
                "url": url,
                "icon": report.get("icon", "fas fa-file-alt"),
            }
        )
    return cards


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, DATE_FMT).date()
    except (TypeError, ValueError):
        return None


def _default_period() -> (date, date):
    today = timezone.localdate()
    start = today - timedelta(days=30)
    return start, today


class ReportListView(UserOrganizationMixin, TemplateView):
    template_name = "accounting/reports/report_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        namespace = self.request.resolver_match.namespace or "accounting"
        context["reports"] = build_report_cards(namespace)

        custom_definitions = ReportDefinition.objects.filter(
            is_active=True,
        ).filter(
            models.Q(organization__isnull=True) | models.Q(organization=self.organization)
        ).order_by("organization_id", "name")
        context["custom_reports"] = custom_definitions

        if self.organization:
            context["journal_udf_filters"] = [
                serialize_udf_definition(udf)
                for udf in filterable_udfs(Journal, self.organization)
            ]
            context["journal_line_udf_pivots"] = [
                serialize_udf_definition(udf)
                for udf in pivot_udfs(JournalLine, self.organization)
            ]
        else:
            context["journal_udf_filters"] = []
            context["journal_line_udf_pivots"] = []
        return context


class GeneralLedgerView(UserOrganizationMixin, View):
    template_name = "accounting/reports/general_ledger.html"

    def get(self, request):
        account_id_raw = request.GET.get("account_id")
        start_raw = request.GET.get("start_date")
        end_raw = request.GET.get("end_date")

        accounts = ChartOfAccount.objects.filter(
            organization=self.organization, is_active=True
        ).order_by("account_code")

        start_date, end_date = _default_period()
        if start := _parse_date(start_raw):
            start_date = start
        if end := _parse_date(end_raw):
            end_date = end

        report_data = None
        error = None
        if start_raw and end_raw:
            try:
                service = ReportService(self.organization)
                service.set_date_range(start_date, end_date)
                account_id = int(account_id_raw) if account_id_raw else None
                report_data = service.generate_general_ledger(account_id=account_id)
            except ValueError as exc:
                error = str(exc)
                logger.warning("General ledger generation error: %s", exc)

        context = {
            "accounts": accounts,
            "selected_account": account_id_raw or "",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "report_data": report_data,
            "error": error,
        }
        return render(request, self.template_name, context)


class TrialBalanceView(UserOrganizationMixin, View):
    template_name = "accounting/reports/trial_balance.html"

    def get(self, request):
        as_of_raw = request.GET.get("as_of_date")
        as_of_date = _parse_date(as_of_raw) or timezone.localdate()

        report_data = None
        error = None
        if as_of_raw:
            try:
                service = ReportService(self.organization)
                report_data = service.generate_trial_balance(as_of_date)
            except ValueError as exc:
                error = str(exc)
                logger.warning("Trial balance generation error: %s", exc)

        context = {
            "as_of_date": as_of_date.isoformat(),
            "report_data": report_data,
            "error": error,
        }
        return render(request, self.template_name, context)


class ProfitLossView(UserOrganizationMixin, View):
    template_name = "accounting/reports/profit_loss.html"

    def get(self, request):
        start_raw = request.GET.get("start_date")
        end_raw = request.GET.get("end_date")
        start_date, end_date = _default_period()
        if start := _parse_date(start_raw):
            start_date = start
        if end := _parse_date(end_raw):
            end_date = end

        report_data = None
        error = None
        if start_raw and end_raw:
            try:
                service = ReportService(self.organization)
                service.set_date_range(start_date, end_date)
                report_data = service.generate_profit_and_loss()
            except ValueError as exc:
                error = str(exc)
                logger.warning("P&L generation error: %s", exc)

        context = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "report_data": report_data,
            "error": error,
        }
        return render(request, self.template_name, context)


class BalanceSheetView(UserOrganizationMixin, View):
    template_name = "accounting/reports/balance_sheet.html"

    def get(self, request):
        as_of_raw = request.GET.get("as_of_date")
        as_of_date = _parse_date(as_of_raw) or timezone.localdate()

        report_data = None
        error = None
        if as_of_raw:
            try:
                service = ReportService(self.organization)
                report_data = service.generate_balance_sheet(as_of_date)
            except ValueError as exc:
                error = str(exc)
                logger.warning("Balance sheet generation error: %s", exc)

        context = {
            "as_of_date": as_of_date.isoformat(),
            "report_data": report_data,
            "error": error,
        }
        return render(request, self.template_name, context)


class CashFlowView(UserOrganizationMixin, View):
    template_name = "accounting/reports/cash_flow.html"

    def get(self, request):
        start_raw = request.GET.get("start_date")
        end_raw = request.GET.get("end_date")
        start_date, end_date = _default_period()
        if start := _parse_date(start_raw):
            start_date = start
        if end := _parse_date(end_raw):
            end_date = end

        report_data = None
        error = None
        if start_raw and end_raw:
            try:
                service = ReportService(self.organization)
                service.set_date_range(start_date, end_date)
                report_data = service.generate_cash_flow()
            except ValueError as exc:
                error = str(exc)
                logger.warning("Cash flow generation error: %s", exc)

        context = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "report_data": report_data,
            "error": error,
        }
        return render(request, self.template_name, context)


class AccountsReceivableAgingView(UserOrganizationMixin, View):
    template_name = "accounting/reports/ar_aging.html"

    def get(self, request):
        as_of_raw = request.GET.get("as_of_date")
        as_of_date = _parse_date(as_of_raw) or timezone.localdate()

        report_data = None
        error = None
        if as_of_raw:
            try:
                service = ReportService(self.organization)
                report_data = service.generate_ar_aging(as_of_date)
            except ValueError as exc:
                error = str(exc)
                logger.warning("A/R aging generation error: %s", exc)

        context = {
            "as_of_date": as_of_date.isoformat(),
            "report_data": report_data,
            "error": error,
        }
        return render(request, self.template_name, context)


class AccountsPayableAgingView(UserOrganizationMixin, View):
    template_name = "accounting/reports/ap_aging.html"

    def get(self, request):
        as_of_raw = request.GET.get("as_of_date")
        as_of_date = _parse_date(as_of_raw) or timezone.localdate()

        report_data = None
        error = None
        if as_of_raw:
            try:
                service = ReportService(self.organization)
                report_data = service.generate_ap_aging(as_of_date)
            except ValueError as exc:
                error = str(exc)
                logger.warning("A/P aging generation error: %s", exc)

        context = {
            "as_of_date": as_of_date.isoformat(),
            "report_data": report_data,
            "error": error,
        }
        return render(request, self.template_name, context)


class SalesSummaryView(UserOrganizationMixin, View):
    template_name = "accounting/reports/sales_summary.html"

    def get(self, request):
        start_raw = request.GET.get("start_date")
        end_raw = request.GET.get("end_date")
        group_by = request.GET.get("group_by", "month")  # month, week, day

        start_date, end_date = _default_period()
        if start := _parse_date(start_raw):
            start_date = start
        if end := _parse_date(end_raw):
            end_date = end

        report_data = None
        error = None
        if start_raw and end_raw:
            try:
                report_data = self.generate_sales_summary(start_date, end_date, group_by)
            except ValueError as exc:
                error = str(exc)
                logger.warning("Sales summary generation error: %s", exc)

        context = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "group_by": group_by,
            "report_data": report_data,
            "error": error,
        }
        return render(request, self.template_name, context)

    def generate_sales_summary(self, start_date, end_date, group_by):
        """Generate sales summary report"""
        from django.db.models import Sum, Count, F, Q
        from django.db.models.functions import TruncMonth, TruncWeek, TruncDay

        # Get sales invoices in date range
        sales = SalesInvoice.objects.filter(
            organization=self.organization,
            invoice_date__range=(start_date, end_date),
            status__in=['posted', 'paid']
        ).select_related('customer')

        # Group by time period
        if group_by == 'month':
            trunc_func = TruncMonth('invoice_date')
        elif group_by == 'week':
            trunc_func = TruncWeek('invoice_date')
        else:  # day
            trunc_func = TruncDay('invoice_date')

        # Sales by period
        sales_by_period = sales.annotate(
            period=trunc_func
        ).values('period').annotate(
            total_sales=Sum('total'),
            total_tax=Sum('tax_total'),
            invoice_count=Count('invoice_id')
        ).order_by('period')

        # Top customers
        top_customers = sales.values('customer__display_name').annotate(
            total_sales=Sum('total'),
            invoice_count=Count('invoice_id')
        ).order_by('-total_sales')[:10]

        # Sales by product (from invoice lines)
        sales_by_product = SalesInvoiceLine.objects.filter(
            invoice__organization=self.organization,
            invoice__invoice_date__range=(start_date, end_date),
            invoice__status__in=['posted', 'paid']
        ).values(
            'product_code', 'description'
        ).annotate(
            total_quantity=Sum('quantity'),
            total_amount=Sum('line_total')
        ).order_by('-total_amount')[:10]

        return {
            'sales_by_period': list(sales_by_period),
            'top_customers': list(top_customers),
            'top_products': list(sales_by_product),
            'total_sales': sales.aggregate(total=Sum('total'))['total'] or 0,
            'total_invoices': sales.count(),
        }


class InventorySummaryView(UserOrganizationMixin, View):
    template_name = "accounting/reports/inventory_summary.html"

    def get(self, request):
        warehouse_id = request.GET.get("warehouse_id")
        low_stock_threshold = request.GET.get("low_stock_threshold", "10")

        try:
            low_stock_threshold = int(low_stock_threshold)
        except ValueError:
            low_stock_threshold = 10

        warehouses = Warehouse.objects.filter(
            organization=self.organization, is_active=True
        ).order_by("name")

        report_data = None
        error = None
        try:
            report_data = self.generate_inventory_summary(warehouse_id, low_stock_threshold)
        except ValueError as exc:
            error = str(exc)
            logger.warning("Inventory summary generation error: %s", exc)

        context = {
            "warehouses": warehouses,
            "selected_warehouse": warehouse_id or "",
            "low_stock_threshold": low_stock_threshold,
            "report_data": report_data,
            "error": error,
        }
        return render(request, self.template_name, context)

    def generate_inventory_summary(self, warehouse_id, low_stock_threshold):
        """Generate inventory summary report"""
        from django.db.models import Sum, F, Q
        from inventory.models import StockLedger

        # Filter by warehouse if specified
        inventory_filter = {'organization': self.organization}
        if warehouse_id:
            inventory_filter['warehouse_id'] = warehouse_id

        # Current stock levels
        stock_summary = InventoryItem.objects.filter(
            **inventory_filter
        ).select_related('product', 'warehouse').values(
            'product__name', 'product__code', 'warehouse__name', 'quantity_on_hand', 'unit_cost'
        ).annotate(
            total_quantity=Sum('quantity_on_hand'),
            total_value=Sum(F('quantity_on_hand') * F('unit_cost'))
        ).order_by('product__name')

        # Add calculated total_value_per_item to each item
        for item in stock_summary:
            item['total_value_per_item'] = item['quantity_on_hand'] * item['unit_cost']

        # Low stock items
        low_stock = InventoryItem.objects.filter(
            **inventory_filter,
            quantity_on_hand__lte=low_stock_threshold,
            quantity_on_hand__gt=0
        ).select_related('product', 'warehouse').order_by('quantity_on_hand')

        # Out of stock
        out_of_stock = InventoryItem.objects.filter(
            **inventory_filter,
            quantity_on_hand__lte=0
        ).select_related('product', 'warehouse')

        # Slow moving items (no movement in last 90 days)
        ninety_days_ago = timezone.now().date() - timedelta(days=90)
        slow_moving = InventoryItem.objects.filter(
            **inventory_filter,
            quantity_on_hand__gt=0
        ).exclude(
            product__stockledger__txn_date__gte=ninety_days_ago
        ).select_related('product', 'warehouse').distinct()

        # Add calculated total_value to slow moving items
        for item in slow_moving:
            item.total_value = item.quantity_on_hand * item.unit_cost

        # Total valuation
        total_valuation = InventoryItem.objects.filter(
            **inventory_filter
        ).aggregate(
            total_value=Sum(F('quantity_on_hand') * F('unit_cost'))
        )['total_value'] or 0

        return {
            'stock_summary': list(stock_summary),
            'low_stock_items': list(low_stock),
            'out_of_stock_items': list(out_of_stock),
            'slow_moving_items': list(slow_moving),
            'total_valuation': total_valuation,
            'total_items': len(stock_summary),
        }


class TaxSummaryView(UserOrganizationMixin, View):
    template_name = "accounting/reports/tax_summary.html"

    def get(self, request):
        start_raw = request.GET.get("start_date")
        end_raw = request.GET.get("end_date")

        start_date, end_date = _default_period()
        if start := _parse_date(start_raw):
            start_date = start
        if end := _parse_date(end_raw):
            end_date = end

        report_data = None
        error = None
        if start_raw and end_raw:
            try:
                report_data = self.generate_tax_summary(start_date, end_date)
            except ValueError as exc:
                error = str(exc)
                logger.warning("Tax summary generation error: %s", exc)

        context = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "report_data": report_data,
            "error": error,
        }
        return render(request, self.template_name, context)

    def generate_tax_summary(self, start_date, end_date):
        """Generate tax summary report for Nepal VAT filing"""
        from django.db.models import Sum, Q

        # Sales tax collected (VAT on sales)
        sales_tax = SalesInvoice.objects.filter(
            organization=self.organization,
            invoice_date__range=(start_date, end_date),
            status__in=['posted', 'paid']
        ).aggregate(
            taxable_sales=Sum('subtotal'),
            tax_collected=Sum('tax_total')
        )

        # Purchase tax paid (VAT on purchases)
        purchase_tax = JournalLine.objects.filter(
            journal__organization=self.organization,
            journal__journal_date__range=(start_date, end_date),
            journal__status='posted',
            account__account_type__nature='liability',  # VAT payable account
            credit_amount__gt=0
        ).aggregate(
            tax_paid=Sum('credit_amount')
        )

        # Tax payable/receivable
        tax_payable = (sales_tax['tax_collected'] or 0) - (purchase_tax['tax_paid'] or 0)

        return {
            'taxable_sales': sales_tax['taxable_sales'] or 0,
            'tax_collected': sales_tax['tax_collected'] or 0,
            'tax_paid': purchase_tax['tax_paid'] or 0,
            'tax_payable': abs(tax_payable),
            'is_payable': tax_payable >= 0,
            'period': f"{start_date} to {end_date}",
        }


class ExpenseSummaryView(UserOrganizationMixin, View):
    template_name = "accounting/reports/expense_summary.html"

    def get(self, request):
        start_raw = request.GET.get("start_date")
        end_raw = request.GET.get("end_date")
        category_filter = request.GET.get("category")

        start_date, end_date = _default_period()
        if start := _parse_date(start_raw):
            start_date = start
        if end := _parse_date(end_raw):
            end_date = end

        report_data = None
        error = None
        if start_raw and end_raw:
            try:
                report_data = self.generate_expense_summary(start_date, end_date, category_filter)
            except ValueError as exc:
                error = str(exc)
                logger.warning("Expense summary generation error: %s", exc)

        # Get expense categories
        expense_accounts = ChartOfAccount.objects.filter(
            organization=self.organization,
            account_type__nature='expense',
            is_active=True
        ).order_by('account_code')

        context = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "category_filter": category_filter or "",
            "expense_accounts": expense_accounts,
            "report_data": report_data,
            "error": error,
        }
        return render(request, self.template_name, context)

    def generate_expense_summary(self, start_date, end_date, category_filter):
        """Generate expense summary report"""
        from django.db.models import Sum, F, Q
        from django.db.models.functions import TruncMonth

        # Filter for expense accounts
        expense_filter = {
            'journal__organization': self.organization,
            'journal__journal_date__range': (start_date, end_date),
            'journal__status': 'posted',
            'debit_amount__gt': 0,
            'account__account_type__nature': 'expense'
        }
        
        if category_filter:
            expense_filter['account_id'] = category_filter

        # Expenses by category
        expenses_by_category = JournalLine.objects.filter(
            **expense_filter
        ).select_related('account').values(
            'account__account_name', 'account__account_code'
        ).annotate(
            total_expense=Sum('debit_amount')
        ).order_by('-total_expense')

        # Expenses by month
        expenses_by_month = JournalLine.objects.filter(
            **expense_filter
        ).annotate(
            month=TruncMonth('journal__journal_date')
        ).values('month').annotate(
            total_expense=Sum('debit_amount')
        ).order_by('month')

        # Total expenses
        total_expenses = JournalLine.objects.filter(
            **expense_filter
        ).aggregate(total=Sum('debit_amount'))['total'] or 0

        # Calculate average monthly expense
        num_months = len(expenses_by_month) if expenses_by_month else 1
        avg_monthly_expense = total_expenses / num_months if num_months > 0 else 0

        return {
            'expenses_by_category': list(expenses_by_category),
            'expenses_by_month': list(expenses_by_month),
            'total_expenses': total_expenses,
            'avg_monthly_expense': avg_monthly_expense,
        }


class CustomReportView(UserOrganizationMixin, View):
    template_name = "accounting/reports/custom_report.html"

    def get_definition(self, code: str) -> ReportDefinition:
        queryset = ReportDefinition.objects.filter(is_active=True).filter(
            models.Q(organization__isnull=True) | models.Q(organization=self.organization)
        )
        return get_object_or_404(queryset, code=code)

    def get(self, request, code: str):
        definition = self.get_definition(code)
        raw_parameters = {k: v for k, v in request.GET.items() if k not in ("code",)}

        report_data = None
        error = None
        parameter_schema = definition.parameter_schema or {}
        require_params = bool(parameter_schema.get("parameters"))

        if raw_parameters or not require_params:
            try:
                typed_params = self._coerce_parameters(parameter_schema, raw_parameters)
                service = ReportService(self.organization)
                report_data = service.run_custom_definition(definition, typed_params)
            except ValueError as exc:
                error = str(exc)
                logger.warning("Custom report generation error for %s: %s", code, exc)

        context = {
            "definition": definition,
            "parameter_schema": parameter_schema,
            "submitted_params": raw_parameters,
            "report_data": report_data,
            "error": error,
        }
        return render(request, self.template_name, context)

    @staticmethod
    def _coerce_parameters(schema: Dict[str, Any], raw: Dict[str, Any]) -> Dict[str, Any]:
        coerced: Dict[str, Any] = {}
        for param in schema.get("parameters", []):
            name = param.get("name")
            if not name:
                continue
            value = raw.get(name, param.get("default"))
            if (value is None or value == "") and param.get("required"):
                raise ValueError(f"Parameter '{name}' is required.")
            param_type = (param.get("type") or "string").lower()
            if value in (None, ""):
                coerced[name] = None
                continue
            try:
                if param_type == "date":
                    coerced[name] = _parse_date(value) or value
                elif param_type in ("int", "integer"):
                    coerced[name] = int(value)
                elif param_type in ("decimal", "number", "numeric"):
                    coerced[name] = Decimal(str(value))
                else:
                    coerced[name] = value
            except Exception as exc:  # noqa: BLE001
                raise ValueError(f"Invalid value for {name}: {value}") from exc
        return coerced


class ReportExportView(UserOrganizationMixin, View):
    """
    Export reports in CSV/Excel/PDF using the stored-procedure data.
    """

    def post(self, request, *args, **kwargs):
        report_type = request.POST.get("report_type")
        export_format = request.POST.get("export_format", "csv").lower()

        service = ReportService(self.organization)
        try:
            report_data = self._generate_report_for_export(service, report_type, request.POST)
        except ValueError as exc:
            logger.warning("Export validation error: %s", exc)
            return self._export_error_response(str(exc))

        try:
            if export_format == "csv":
                file_buffer, filename = ReportExportService.to_csv(report_data)
                content_type = "text/csv"
            elif export_format == "excel":
                file_buffer, filename = ReportExportService.to_excel(report_data)
                content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            elif export_format == "pdf":
                file_buffer, filename = ReportExportService.to_pdf(report_data)
                content_type = "application/pdf"
            else:
                raise ValueError(f"Unsupported export format: {export_format}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Export failed:")
            return self._export_error_response(str(exc))

        response = HttpResponse(file_buffer.getvalue(), content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    def _generate_report_for_export(self, service: ReportService, report_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if report_type == "general_ledger":
            start = _parse_date(data.get("start_date"))
            end = _parse_date(data.get("end_date"))
            if not (start and end):
                raise ValueError("Start and end dates are required for the general ledger export.")
            service.set_date_range(start, end)
            account_id = int(data["account_id"]) if data.get("account_id") else None
            return service.generate_general_ledger(account_id=account_id)

        if report_type == "trial_balance":
            as_of = _parse_date(data.get("as_of_date"))
            if not as_of:
                raise ValueError("As of date is required for the trial balance export.")
            return service.generate_trial_balance(as_of)

        if report_type == "profit_loss":
            start = _parse_date(data.get("start_date"))
            end = _parse_date(data.get("end_date"))
            if not (start and end):
                raise ValueError("Start and end dates are required for the profit & loss export.")
            service.set_date_range(start, end)
            return service.generate_profit_and_loss()

        if report_type == "balance_sheet":
            as_of = _parse_date(data.get("as_of_date"))
            if not as_of:
                raise ValueError("As of date is required for the balance sheet export.")
            return service.generate_balance_sheet(as_of)

        if report_type == "cash_flow":
            start = _parse_date(data.get("start_date"))
            end = _parse_date(data.get("end_date"))
            if not (start and end):
                raise ValueError("Start and end dates are required for the cash flow export.")
            service.set_date_range(start, end)
            return service.generate_cash_flow()

        if report_type == "ar_aging":
            as_of = _parse_date(data.get("as_of_date"))
            if not as_of:
                raise ValueError("As of date is required for the aging export.")
            return service.generate_ar_aging(as_of)

        if report_type == "ap_aging":
            as_of = _parse_date(data.get("as_of_date"))
            if not as_of:
                raise ValueError("As of date is required for the aging export.")
            return service.generate_ap_aging(as_of)

        if report_type and report_type.startswith("custom:"):
            code = report_type.split(":", 1)[1]
            queryset = ReportDefinition.objects.filter(is_active=True).filter(
                models.Q(organization__isnull=True) | models.Q(organization=self.organization)
            )
            definition = get_object_or_404(queryset, code=code)
            params = {k: v for k, v in data.items() if k not in {"report_type", "export_format", "csrfmiddlewaretoken"}}
            typed_params = CustomReportView._coerce_parameters(definition.parameter_schema or {}, params)
            return service.run_custom_definition(definition, typed_params)

        raise ValueError(f"Unsupported report type: {report_type}")

    def _export_error_response(self, message: str) -> HttpResponse:
        response = HttpResponse(message, content_type="text/plain", status=400)
        return response
