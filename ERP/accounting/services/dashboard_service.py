from __future__ import annotations

from decimal import Decimal
import csv
from io import StringIO
from typing import Any, Dict

from django.db.models import Sum

from accounting.models import (
    AccountType,
    Asset,
    BankAccount,
    Budget,
    GeneralLedger,
    PurchaseInvoice,
    SalesInvoice,
    TaxLiability,
)
from accounting.services.ap_aging_service import APAgingService
from accounting.services.budget_service import BudgetService


class DashboardService:
    """Aggregates KPI data for CP/BI dashboards."""

    def __init__(self, organization):
        self.organization = organization
        self.aging_service = APAgingService(organization)
        self._ap_bucket_labels = self.aging_service.bucket_labels()

    def get_ap_aging_detail(self) -> Dict[str, Any]:
        rows = self.aging_service.build()
        headers = self._ap_bucket_labels
        detail_rows = []
        for row in rows:
            detail_rows.append(
                {
                    "vendor_name": row.vendor_name,
                    "buckets": [
                        row.buckets.get(label, Decimal('0')) for label in headers
                    ],
                    "total": row.total,
                }
            )
        return {"headers": headers, "rows": detail_rows}

    def get_ap_aging_summary(self) -> Dict[str, Any]:
        summary = self.aging_service.summarize()
        return {
            "buckets": summary,
            "total": summary.get("grand_total"),
        }

    def get_cash_summary(self) -> Dict[str, Any]:
        totals = BankAccount.objects.filter(
            organization=self.organization, is_active=True
        ).aggregate(balance=Sum("current_balance"))
        return {"cash_balance": totals["balance"] or 0}

    def get_budget_variance_summary(self) -> Dict[str, Any]:
        budget = Budget.objects.filter(organization=self.organization, status="approved").last()
        if not budget:
            return {"variances": [], "total_budget": 0}
        service = BudgetService(budget)
        rows = service.calculate_variances()
        total_budget = sum(row.budget_amount for row in rows)
        total_actual = sum(row.actual_amount for row in rows)
        return {
            "total_budget": total_budget,
            "total_actual": total_actual,
            "variances": [
                {
                    "account": row.account_name,
                    "budget": row.budget_amount,
                    "actual": row.actual_amount,
                    "variance": row.variance,
                }
                for row in rows
            ],
        }

    def get_asset_summary(self) -> Dict[str, Any]:
        assets = Asset.objects.filter(organization=self.organization, status="active")
        total_cost = assets.aggregate(cost=Sum("cost"))["cost"] or 0
        total_book = sum(asset.book_value for asset in assets)
        return {"total_cost": total_cost, "book_value": total_book, "count": assets.count()}

    def get_tax_liabilities(self) -> Dict[str, Any]:
        liabilities = TaxLiability.objects.filter(organization=self.organization)
        total_payable = liabilities.filter(amount__gt=0).aggregate(payable=Sum("amount"))["payable"] or 0
        total_receivable = liabilities.filter(amount__lt=0).aggregate(receivable=Sum("amount"))["receivable"] or 0
        return {"total_payable": total_payable, "total_receivable": total_receivable}

    def get_ar_aging_summary(self) -> Dict[str, Any]:
        outstanding = (
            SalesInvoice.objects.filter(
                organization=self.organization, status__in=["posted", "validated"]
            )
            .aggregate(total=Sum("total"))
            .get("total")
        )
        return {"ar_outstanding": outstanding or 0}

    def get_dashboard_metrics(self) -> Dict[str, Any]:
        return {
            "ap_aging": self.get_ap_aging_summary(),
            "ap_aging_detail": self.get_ap_aging_detail(),
            "ar_aging": self.get_ar_aging_summary(),
            "cash": self.get_cash_summary(),
            "budget_variance": self.get_budget_variance_summary(),
            "assets": self.get_asset_summary(),
            "tax_liabilities": self.get_tax_liabilities(),
        }

    def export_csv(self) -> str:
        metrics = self.get_dashboard_metrics()
        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["metric", "value"])
        writer.writerow(["AP aging total", metrics["ap_aging"]["total"]])
        writer.writerow(["AR outstanding", metrics["ar_aging"]["ar_outstanding"]])
        writer.writerow(["Cash balance", metrics["cash"]["cash_balance"]])
        writer.writerow(["Budget plan total", metrics["budget_variance"]["total_budget"]])
        writer.writerow(["Budget actual total", metrics["budget_variance"]["total_actual"]])
        writer.writerow(["Asset book value", metrics["assets"]["book_value"]])
        writer.writerow(["Tax payable", metrics["tax_liabilities"]["total_payable"]])
        writer.writerow(["Tax receivable", metrics["tax_liabilities"]["total_receivable"]])
        return buffer.getvalue()
