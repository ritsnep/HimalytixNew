from __future__ import annotations

from collections import defaultdict, OrderedDict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Sequence

from django.db import connection
from django.urls import reverse
from django.utils import timezone

from accounting.models import FiscalYear, ReportDefinition
from accounting.services.ap_aging_service import APAgingService
from usermanagement.models import Organization


ZERO = Decimal("0.00")


@dataclass
class ReportParameter:
    """Utility structure for strongly typed custom report parameters."""

    name: str
    param_type: str = "string"
    required: bool = False
    default: Any = None
    help_text: Optional[str] = None


class ReportService:
    """
    High-performance financial reporting service backed by database functions.

    Each public method returns a dictionary that templates and exporters understand.
    Data is sourced from PostgreSQL stored procedures (see migrations/0110).
    """

    def __init__(self, organization: Organization):
        self.organization = organization
        self.start_date: Optional[date] = None
        self.end_date: Optional[date] = None
        self.as_of_date: Optional[date] = None

    # ------------------------------------------------------------------
    # Date helpers

    def set_date_range(self, start_date: date, end_date: date) -> None:
        if start_date is None or end_date is None:
            raise ValueError("A valid start and end date are required.")
        if start_date > end_date:
            raise ValueError("Start date cannot be after end date.")
        self.start_date = start_date
        self.end_date = end_date

    def set_as_of_date(self, as_of: date) -> None:
        if as_of is None:
            raise ValueError("A valid 'as of' date is required.")
        self.as_of_date = as_of

    # ------------------------------------------------------------------
    # Core data access helpers

    def _call_function(self, function_name: str, params: Sequence[Any]) -> List[Dict[str, Any]]:
        """
        Execute a reporting function and return rows as dictionaries.
        """
        placeholders = ", ".join(["%s"] * len(params))
        sql = f"SELECT * FROM {function_name}({placeholders});" if params else f"SELECT * FROM {function_name}();"

        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()

        return [dict(zip(columns, row)) for row in rows]

    def _start_of_fiscal_year(self) -> Optional[date]:
        """
        Resolve the current fiscal year's starting date for the organization.
        """
        fy = (
            FiscalYear.objects.filter(organization=self.organization, is_current=True)
            .order_by("-start_date")
            .first()
        )
        return fy.start_date if fy else None

    # ------------------------------------------------------------------
    # General Ledger

    def generate_general_ledger(self, account_id: Optional[int] = None) -> Dict[str, Any]:
        if not (self.start_date and self.end_date):
            raise ValueError("Call set_date_range() before generating the general ledger.")

        rows = self._call_function(
            "fn_report_general_ledger",
            [self.organization.id, self.start_date, self.end_date, account_id],
        )

        totals = {
            "total_debit": ZERO,
            "total_credit": ZERO,
            "opening_balance": ZERO,
            "ending_balance": ZERO,
        }
        account_summary: Dict[int, Dict[str, Any]] = OrderedDict()
        lines: List[Dict[str, Any]] = []

        for row in rows:
            debit = row.get("debit_amount") or ZERO
            credit = row.get("credit_amount") or ZERO
            running = row.get("running_balance") or ZERO
            opening = row.get("opening_balance") or ZERO

            totals["total_debit"] += debit
            totals["total_credit"] += credit

            account_id_value = row.get("account_id")
            if account_id_value is not None:
                summary = account_summary.setdefault(
                    account_id_value,
                    {
                        "account_id": account_id_value,
                        "account_code": row.get("account_code"),
                        "account_name": row.get("account_name"),
                        "opening_balance": opening,
                        "closing_balance": running,
                        "detail_url": self._ledger_detail_url(account_id_value),
                    },
                )
                summary["closing_balance"] = running

            line = {
                "date": row.get("transaction_date"),
                "account_id": account_id_value,
                "account_code": row.get("account_code"),
                "account_name": row.get("account_name"),
                "journal_id": row.get("journal_id"),
                "journal_no": row.get("journal_number"),
                "reference": row.get("reference"),
                "description": row.get("line_description"),
                "debit": debit,
                "credit": credit,
                "balance": running,
                "running_balance": running,
                "journal_line_id": row.get("journal_line_id"),
                "journal_url": self._journal_url(row.get("journal_id")),
            }
            lines.append(line)

        if account_summary:
            totals["opening_balance"] = sum(info["opening_balance"] for info in account_summary.values())
            totals["ending_balance"] = sum(info["closing_balance"] for info in account_summary.values())

        report = {
            "report_type": "general_ledger",
            "organization": self.organization.name,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "generated_at": timezone.now(),
            "lines": lines,
            "accounts": list(account_summary.values()),
            "totals": totals,
        }
        return report

    # ------------------------------------------------------------------
    # Trial Balance

    def generate_trial_balance(self, as_of: Optional[date] = None) -> Dict[str, Any]:
        as_of_date = as_of or self.as_of_date
        if not as_of_date:
            raise ValueError("An 'as of' date is required for the trial balance.")

        rows = self._call_function(
            "fn_report_trial_balance",
            [self.organization.id, as_of_date],
        )

        lines: List[Dict[str, Any]] = []
        total_debits = ZERO
        total_credits = ZERO

        for row in rows:
            debit_total = row.get("debit_total") or ZERO
            credit_total = row.get("credit_total") or ZERO

            total_debits += debit_total
            total_credits += credit_total

            account_id_value = row.get("account_id")
            lines.append(
                {
                    "account_id": account_id_value,
                    "account_code": row.get("account_code"),
                    "account_name": row.get("account_name"),
                    "account_type": (row.get("account_nature") or "").title(),
                    "debit_balance": debit_total,
                    "credit_balance": credit_total,
                    "detail_url": self._ledger_detail_url(
                        account_id_value,
                        start_date=self._start_of_fiscal_year() or (as_of_date.replace(month=1, day=1)),
                        end_date=as_of_date,
                    ),
                }
            )

        is_balanced = abs(total_debits - total_credits) < Decimal("0.005")

        return {
            "report_type": "trial_balance",
            "organization": self.organization.name,
            "as_of_date": as_of_date,
            "generated_at": timezone.now(),
            "lines": lines,
            "totals": {
                "total_debits": total_debits,
                "total_credits": total_credits,
                "difference": total_debits - total_credits,
            },
            "is_balanced": is_balanced,
        }

    # ------------------------------------------------------------------
    # Profit & Loss

    def generate_profit_and_loss(self) -> Dict[str, Any]:
        if not (self.start_date and self.end_date):
            raise ValueError("Call set_date_range() before generating the profit & loss statement.")

        rows = self._call_function(
            "fn_report_profit_loss",
            [self.organization.id, self.start_date, self.end_date],
        )

        sections: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        totals = {
            "total_income": ZERO,
            "total_expense": ZERO,
        }

        for row in rows:
            category = row.get("category") or row.get("account_nature") or "Uncategorised"
            nature = row.get("account_nature")
            net_amount = row.get("net_amount") or ZERO
            debit_total = row.get("debit_total") or ZERO
            credit_total = row.get("credit_total") or ZERO

            section = sections.setdefault(
                category,
                {
                    "category": category,
                    "nature": nature,
                    "accounts": [],
                    "total": ZERO,
                },
            )
            section["accounts"].append(
                {
                    "account_id": row.get("account_id"),
                    "account_code": row.get("account_code"),
                    "account_name": row.get("account_name"),
                    "debit": debit_total,
                    "credit": credit_total,
                    "net": net_amount,
                    "detail_url": self._ledger_detail_url(
                        row.get("account_id"),
                        start_date=self.start_date,
                        end_date=self.end_date,
                    ),
                }
            )
            section["total"] += net_amount

            if nature == "income":
                totals["total_income"] += net_amount
            else:
                totals["total_expense"] += net_amount

        net_profit = totals["total_income"] - totals["total_expense"]

        return {
            "report_type": "profit_loss",
            "organization": self.organization.name,
            "period": f"{self.start_date} – {self.end_date}",
            "generated_at": timezone.now(),
            "sections": list(sections.values()),
            "totals": {
                **totals,
                "net_profit": net_profit,
            },
        }

    # ------------------------------------------------------------------
    # Balance Sheet

    def generate_balance_sheet(self, as_of: Optional[date] = None) -> Dict[str, Any]:
        as_of_date = as_of or self.as_of_date
        if not as_of_date:
            raise ValueError("An 'as of' date is required for the balance sheet.")

        rows = self._call_function(
            "fn_report_balance_sheet",
            [self.organization.id, as_of_date],
        )

        lines: List[Dict[str, Any]] = []
        totals = defaultdict(lambda: ZERO)

        for row in rows:
            balance = row.get("balance") or ZERO
            nature = row.get("nature")
            category = row.get("category") or nature

            lines.append(
                {
                    "account_id": row.get("account_id"),
                    "account_code": row.get("account_code"),
                    "account_name": row.get("account_name"),
                    "line_type": nature,
                    "category": category,
                    "amount": balance,
                    "detail_url": self._ledger_detail_url(
                        row.get("account_id"),
                        start_date=self._start_of_fiscal_year() or as_of_date.replace(month=1, day=1),
                        end_date=as_of_date,
                    ),
                }
            )
            totals[nature] += balance

        assets = totals.get("asset", ZERO)
        liabilities = totals.get("liability", ZERO)
        equity = totals.get("equity", ZERO)

        return {
            "report_type": "balance_sheet",
            "organization": self.organization.name,
            "as_of_date": as_of_date,
            "generated_at": timezone.now(),
            "lines": lines,
            "totals": {
                "total_assets": assets,
                "total_liabilities": liabilities,
                "total_equity": equity,
                "total_liabilities_equity": liabilities + equity,
                "difference": assets - (liabilities + equity),
            },
            "is_balanced": abs(assets - (liabilities + equity)) < Decimal("0.01"),
        }

    # ------------------------------------------------------------------
    # Cash Flow

    def generate_cash_flow(self) -> Dict[str, Any]:
        if not (self.start_date and self.end_date):
            raise ValueError("Call set_date_range() before generating the cash flow statement.")

        rows = self._call_function(
            "fn_report_cash_flow",
            [self.organization.id, self.start_date, self.end_date],
        )

        categories: Dict[str, Dict[str, Any]] = OrderedDict()

        for row in rows:
            category = row.get("category") or "Uncategorised"
            amount = row.get("cash_movement") or ZERO

            bucket = categories.setdefault(
                category,
                {
                    "category": category,
                    "accounts": [],
                    "total": ZERO,
                },
            )
            bucket["accounts"].append(
                {
                    "account_id": row.get("account_id"),
                    "account_code": row.get("account_code"),
                    "account_name": row.get("account_name"),
                    "amount": amount,
                }
            )
            bucket["total"] += amount

        net_change = sum(bucket["total"] for bucket in categories.values())

        return {
            "report_type": "cash_flow",
            "organization": self.organization.name,
            "period": f"{self.start_date} – {self.end_date}",
            "generated_at": timezone.now(),
            "categories": list(categories.values()),
            "totals": {
                "net_change": net_change,
            },
        }

    # ------------------------------------------------------------------
    # Accounts Receivable Aging

    def generate_ar_aging(self, as_of: Optional[date] = None) -> Dict[str, Any]:
        as_of_date = as_of or self.as_of_date
        if not as_of_date:
            raise ValueError("An 'as of' date is required for the aging report.")

        rows = self._call_function(
            "fn_report_ar_aging",
            [self.organization.id, as_of_date],
        )

        aging_summary = defaultdict(lambda: ZERO)
        lines: List[Dict[str, Any]] = []

        for row in rows:
            balance = row.get("balance") or ZERO
            bucket = row.get("bucket") or "Uncategorised"
            aging_summary[bucket] += balance

            lines.append(
                {
                    "account_id": row.get("account_id"),
                    "account_code": row.get("account_code"),
                    "account_name": row.get("account_name"),
                    "bucket": bucket,
                    "balance": balance.copy_abs() if hasattr(balance, "copy_abs") else abs(balance),
                }
            )

        total_ar = sum(aging_summary.values())

        ordered_buckets = sorted(aging_summary.items(), key=lambda item: item[0])

        return {
            "report_type": "ar_aging",
            "organization": self.organization.name,
            "as_of_date": as_of_date,
            "generated_at": timezone.now(),
            "lines": lines,
            "aging_summary": [
                {"bucket": bucket, "balance": amount} for bucket, amount in ordered_buckets
            ],
            "total": total_ar,
        }

    def generate_ap_aging(self, as_of: Optional[date] = None) -> Dict[str, Any]:
        as_of_date = as_of or self.as_of_date
        if not as_of_date:
            raise ValueError("An 'as of' date is required for the aging report.")

        service = APAgingService(self.organization, reference_date=as_of_date)
        rows = service.build()
        summary = service.summarize()

        lines: List[Dict[str, Any]] = []
        for row in rows:
            for bucket, amount in row.buckets.items():
                lines.append(
                    {
                        "vendor_id": row.vendor_id,
                        "vendor_name": row.vendor_name,
                        "bucket": bucket,
                        "balance": amount,
                    }
                )

        aging_summary = [
            {"bucket": bucket, "balance": amount}
            for bucket, amount in summary.items()
            if bucket != "grand_total"
        ]

        return {
            "report_type": "ap_aging",
            "organization": self.organization.name,
            "as_of_date": as_of_date,
            "generated_at": timezone.now(),
            "lines": lines,
            "aging_summary": aging_summary,
            "total": summary.get("grand_total", ZERO),
        }

    # ------------------------------------------------------------------
    # Custom stored-procedure reports

    def run_custom_definition(self, definition: ReportDefinition, raw_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a user-defined stored procedure and return dynamic results.
        """
        if not definition.is_active:
            raise ValueError("The requested report definition is inactive.")
        if definition.organization and definition.organization_id != self.organization.id:
            raise PermissionError("Report definition does not belong to this organization.")

        param_schema = definition.parameter_schema or {}
        schema_params = [
            ReportParameter(**param_descriptor)
            for param_descriptor in param_schema.get("parameters", [])
        ]

        ordered_values: List[Any] = []
        params = raw_params or {}
        for descriptor in schema_params:
            value = params.get(descriptor.name, descriptor.default)
            if (value in (None, "", [])) and descriptor.required:
                raise ValueError(f"Parameter '{descriptor.name}' is required.")
            ordered_values.append(value)

        result_rows = self._call_function(definition.stored_procedure, ordered_values)

        columns: List[str] = list(result_rows[0].keys()) if result_rows else []

        return {
            "report_type": definition.code,
            "name": definition.name,
            "organization": self.organization.name,
            "generated_at": timezone.now(),
            "columns": columns,
            "rows": result_rows,
            "parameters": params,
            "definition_id": definition.report_id,
        }

    # ------------------------------------------------------------------
    # URL helpers

    def _journal_url(self, journal_id: Optional[int]) -> Optional[str]:
        if not journal_id:
            return None
        try:
            return reverse("accounting:journal_entry_detail", args=[journal_id])
        except Exception:
            return None

    def _ledger_detail_url(
        self,
        account_id: Optional[int],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Optional[str]:
        if not account_id:
            return None
        try:
            url = reverse("accounting:report_ledger")
        except Exception:
            return None

        query_params = [f"account_id={account_id}"]
        if start_date:
            query_params.append(f"start_date={start_date.isoformat()}")
        if end_date:
            query_params.append(f"end_date={end_date.isoformat()}")
        return f"{url}?{'&'.join(query_params)}"
