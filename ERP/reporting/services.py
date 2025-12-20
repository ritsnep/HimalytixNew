from __future__ import annotations

import io
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from django.db import connection
from django.db.models import Prefetch
from django.utils import timezone

from accounting.models import Journal, JournalLine
from accounting.services.report_service import ReportService as AccountingReportService
from reporting.models import ReportDefinition
from reporting.utils import (
    export_csv,
    export_excel,
    export_pdf,
    render_base_template,
    render_template_string,
    sanitize_template_html,
)


def _parse_date(value: Any, default: Optional[date] = None) -> Optional[date]:
    if value in (None, "", []):
        return default
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value)).date()
    except Exception:
        return default


class ReportDataService:
    """Fetches data and builds a normalized context for templating/export."""

    def __init__(self, organization, user=None):
        self.organization = organization
        self.user = user

    @staticmethod
    def _get_status_display(status: str) -> str:
        """Convert status code to display label."""
        status_map = {
            "draft": "Draft",
            "awaiting_approval": "Awaiting Approval",
            "approved": "Approved",
            "posted": "Posted",
            "reversed": "Reversed",
            "rejected": "Rejected",
        }
        return status_map.get(status, status.title())

    def build_context(self, definition: ReportDefinition, params: Dict[str, Any]) -> Dict[str, Any]:
        """Return context payload for the requested report definition."""
        code = (definition.code or "").lower()
        context: Dict[str, Any]

        if definition.template_json and definition.template_json.get("query_builder"):
            context = self._query_builder_context(definition.template_json.get("query_builder"), params)
        elif code in {"daybook", "day_book"} or definition.query_name == "fn_report_daybook":
            context = self._daybook_report_context(params)
        elif code in {"journal_report", "journal"} or definition.query_name == "fn_report_journal":
            context = self._journal_report_context(params)
        elif code in {"general_ledger", "ledger"} or definition.query_name == "fn_report_general_ledger":
            context = self._general_ledger_context(params)
        elif code in {"trial_balance"} or definition.query_name == "fn_report_trial_balance":
            context = self._trial_balance_context(params)
        elif code in {"profit_loss", "profit_and_loss"} or definition.query_name == "fn_report_profit_loss":
            context = self._profit_loss_context(params)
        elif code in {"balance_sheet"} or definition.query_name == "fn_report_balance_sheet":
            context = self._balance_sheet_context(params)
        elif definition.query_name:
            context = self._call_stored_procedure(definition.query_name, params)
        else:
            context = {"rows": [], "columns": [], "totals": {}}

        base: Dict[str, Any] = {
            "definition": definition,
            "organization": self.organization,
            "generated_at": timezone.now(),
            "filters": params,
            "title": definition.name or definition.code.replace("_", " ").title(),
        }
        base.update(context)
        base.setdefault("columns", [])
        base.setdefault("rows", [])
        return base

    # ------------------------------------------------------------------
    # Journal report (pilot)

    def _daybook_report_context(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Builds a comprehensive daybook report context with all transactions."""
        today = timezone.localdate()
        default_start = today - timedelta(days=30)
        start_date = _parse_date(params.get("start_date"), default_start)
        end_date = _parse_date(params.get("end_date"), today)
        status = params.get("status")
        journal_type_param = params.get("journal_type")
        account_param = params.get("account_id")
        voucher_number = params.get("voucher_number")
        limit = params.get("limit")

        qs = (
            Journal.objects.filter(
                organization=self.organization,
                journal_date__range=(start_date, end_date),
                is_archived=False,
            )
            .select_related("journal_type", "period", "created_by")
            .prefetch_related(
                Prefetch(
                    "lines",
                    queryset=JournalLine.objects.select_related(
                        "account", "department", "project", "cost_center"
                    ).order_by("line_number"),
                )
            )
            .order_by("journal_date", "journal_number")
        )

        if status:
            qs = qs.filter(status=status)
        if journal_type_param:
            if journal_type_param.isdigit():
                qs = qs.filter(journal_type_id=int(journal_type_param))
            else:
                qs = qs.filter(journal_type__code=journal_type_param)
        if voucher_number:
            qs = qs.filter(journal_number__icontains=voucher_number)

        if limit:
            try:
                qs = qs[: int(limit)]
            except (TypeError, ValueError):
                pass

        rows: List[Dict[str, Any]] = []
        flat_rows: List[List[Any]] = []
        total_debit = Decimal("0.00")
        total_credit = Decimal("0.00")
        transaction_count = 0

        for journal in qs:
            transaction_count += 1
            for line in journal.lines.all():
                debit = line.debit_amount or Decimal("0.00")
                credit = line.credit_amount or Decimal("0.00")
                total_debit += debit
                total_credit += credit

                # Filter by account if specified
                if account_param:
                    try:
                        if line.account_id != int(account_param):
                            continue
                    except (TypeError, ValueError):
                        continue

                row_data = {
                    "journal_id": journal.pk,
                    "journal_date": journal.journal_date,
                    "journal_number": journal.journal_number,
                    "journal_type": getattr(journal.journal_type, "name", ""),
                    "journal_type_name": getattr(journal.journal_type, "name", ""),
                    "journal_type_code": getattr(journal.journal_type, "code", ""),
                    "reference": journal.reference or "",
                    "line_number": line.line_number,
                    "account_code": getattr(line.account, "account_code", ""),
                    "account_name": getattr(line.account, "account_name", ""),
                    "description": line.description or journal.description or "",
                    "debit": debit,
                    "credit": credit,
                    "department": getattr(line.department, "name", ""),
                    "project": getattr(line.project, "name", ""),
                    "cost_center": getattr(line.cost_center, "name", ""),
                    "status": journal.status,
                    "status_display": self._get_status_display(journal.status),
                    "created_by": getattr(journal.created_by, "get_full_name", lambda: "")() or getattr(journal.created_by, "username", ""),
                    "created_at": journal.created_at,
                }
                rows.append(row_data)
                flat_rows.append(
                    [
                        journal.journal_date,
                        journal.journal_number,
                        journal.journal_type.name if journal.journal_type else "",
                        line.account.account_code if line.account else "",
                        line.account.account_name if line.account else "",
                        line.description or journal.description or "",
                        debit,
                        credit,
                        journal.status,
                    ]
                )

        columns = [
            "Date",
            "Voucher #",
            "Type",
            "Account Code",
            "Account Name",
            "Description",
            "Debit",
            "Credit",
            "Status",
        ]

        return {
            "rows": rows,
            "columns": columns,
            "flat_rows": flat_rows,
            "totals": {
                "debit": total_debit,
                "credit": total_credit,
                "balance": total_debit - total_credit,
                "transaction_count": transaction_count,
            },
            "filters": {
                "start_date": start_date,
                "end_date": end_date,
                "status": status,
                "journal_type": journal_type_param,
                "account_id": account_param,
                "voucher_number": voucher_number,
            },
        }

    def _journal_report_context(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Builds a rich context for the journal report."""
        today = timezone.localdate()
        default_start = today - timedelta(days=30)
        start_date = _parse_date(params.get("start_date"), default_start)
        end_date = _parse_date(params.get("end_date"), today)
        status = params.get("status")
        journal_type_param = params.get("journal_type")
        group_by = (params.get("group_by") or "voucher").lower()
        limit = params.get("limit")

        qs = (
            Journal.objects.filter(
                organization=self.organization,
                journal_date__range=(start_date, end_date),
                is_archived=False,
            )
            .select_related("journal_type", "period", "created_by")
            .prefetch_related(
                Prefetch(
                    "lines",
                    queryset=JournalLine.objects.select_related(
                        "account", "department", "project", "cost_center"
                    ).order_by("line_number"),
                )
            )
            .order_by("journal_date", "journal_number")
        )

        if status:
            qs = qs.filter(status=status)
        if journal_type_param:
            if journal_type_param.isdigit():
                qs = qs.filter(journal_type_id=int(journal_type_param))
            else:
                qs = qs.filter(journal_type__code=journal_type_param)

        if limit:
            try:
                qs = qs[: int(limit)]
            except (TypeError, ValueError):
                pass

        rows: List[Dict[str, Any]] = []
        flat_rows: List[List[Any]] = []
        total_debit = Decimal("0.00")
        total_credit = Decimal("0.00")

        for journal in qs:
            lines_payload = []
            for line in journal.lines.all():
                debit = line.debit_amount or Decimal("0.00")
                credit = line.credit_amount or Decimal("0.00")
                total_debit += debit
                total_credit += credit
                line_ctx = {
                    "line_number": line.line_number,
                    "account_code": getattr(line.account, "account_code", ""),
                    "account_name": getattr(line.account, "account_name", ""),
                    "description": line.description,
                    "debit": debit,
                    "credit": credit,
                    "department": getattr(line.department, "name", ""),
                    "project": getattr(line.project, "name", ""),
                    "cost_center": getattr(line.cost_center, "name", ""),
                }
                lines_payload.append(line_ctx)
                flat_rows.append(
                    [
                        journal.journal_date,
                        journal.journal_number,
                        journal.journal_type.name if journal.journal_type else "",
                        line_ctx["account_code"],
                        line_ctx["account_name"],
                        line.description or journal.description or "",
                        debit,
                        credit,
                        journal.status,
                    ]
                )

            rows.append(
                {
                    "journal_id": journal.pk,
                    "journal_number": journal.journal_number,
                    "journal_date": journal.journal_date,
                    "reference": journal.reference,
                    "description": journal.description,
                    "journal_type": journal.journal_type.name if journal.journal_type else "",
                    "status": journal.status,
                    "total_debit": journal.total_debit,
                    "total_credit": journal.total_credit,
                    "group_key": journal.journal_date if group_by == "date" else journal.journal_number,
                    "lines": lines_payload,
                }
            )

        columns = [
            "Date",
            "Journal #",
            "Journal Type",
            "Account",
            "Account Name",
            "Description",
            "Debit",
            "Credit",
            "Status",
        ]

        return {
            "rows": rows,
            "columns": columns,
            "flat_rows": flat_rows,
            "totals": {
                "debit": total_debit,
                "credit": total_credit,
                "balance": total_debit - total_credit,
            },
            "filters": {
                "start_date": start_date,
                "end_date": end_date,
                "status": status,
                "journal_type": journal_type_param,
                "group_by": group_by,
            },
        }

    # ------------------------------------------------------------------
    # Accounting service-backed reports

    def _general_ledger_context(self, params: Dict[str, Any]) -> Dict[str, Any]:
        service = AccountingReportService(self.organization)
        today = timezone.localdate()
        start_default = today - timedelta(days=30)
        start_date = _parse_date(params.get("start_date"), start_default)
        end_date = _parse_date(params.get("end_date"), today)
        service.set_date_range(start_date, end_date)
        account_id = params.get("account_id")
        if account_id:
            try:
                account_id = int(account_id)
            except (TypeError, ValueError):
                account_id = None
        data = service.generate_general_ledger(account_id=account_id)
        columns = [
            "Date",
            "Account",
            "Journal #",
            "Reference",
            "Description",
            "Debit",
            "Credit",
            "Balance",
        ]
        flat_rows = []
        for line in data.get("lines", []):
            flat_rows.append(
                [
                    line.get("date"),
                    f"{line.get('account_code')} {line.get('account_name')}".strip(),
                    line.get("journal_no"),
                    line.get("reference"),
                    line.get("description"),
                    line.get("debit"),
                    line.get("credit"),
                    line.get("running_balance") or line.get("balance"),
                ]
            )
        data["columns"] = columns
        data["flat_rows"] = flat_rows
        data.setdefault("filters", {})
        data["filters"].update({"start_date": start_date, "end_date": end_date, "account_id": account_id})
        data["title"] = data.get("name") or "General Ledger"
        return data

    def _trial_balance_context(self, params: Dict[str, Any]) -> Dict[str, Any]:
        service = AccountingReportService(self.organization)
        as_of = _parse_date(params.get("as_of_date"), timezone.localdate())
        data = service.generate_trial_balance(as_of)
        columns = ["Account Code", "Account Name", "Type", "Debit", "Credit"]
        flat_rows = []
        for line in data.get("lines", []):
            flat_rows.append(
                [
                    line.get("account_code"),
                    line.get("account_name"),
                    line.get("account_type"),
                    line.get("debit_balance"),
                    line.get("credit_balance"),
                ]
            )
        data["columns"] = columns
        data["flat_rows"] = flat_rows
        data.setdefault("filters", {})
        data["filters"].update({"as_of_date": as_of})
        data["title"] = data.get("name") or "Trial Balance"
        return data

    def _profit_loss_context(self, params: Dict[str, Any]) -> Dict[str, Any]:
        service = AccountingReportService(self.organization)
        today = timezone.localdate()
        start_default = today - timedelta(days=30)
        start_date = _parse_date(params.get("start_date"), start_default)
        end_date = _parse_date(params.get("end_date"), today)
        service.set_date_range(start_date, end_date)
        data = service.generate_profit_and_loss()
        columns = ["Account Code", "Account Name", "Debit", "Credit", "Net"]
        flat_rows = []
        for section in data.get("sections", []):
            for account in section.get("accounts", []):
                flat_rows.append(
                    [
                        account.get("account_code"),
                        account.get("account_name"),
                        account.get("debit"),
                        account.get("credit"),
                        account.get("net"),
                    ]
                )
        data["columns"] = columns
        data["flat_rows"] = flat_rows
        data.setdefault("filters", {})
        data["filters"].update({"start_date": start_date, "end_date": end_date})
        data["title"] = data.get("name") or "Profit & Loss"
        return data

    def _balance_sheet_context(self, params: Dict[str, Any]) -> Dict[str, Any]:
        service = AccountingReportService(self.organization)
        as_of = _parse_date(params.get("as_of_date"), timezone.localdate())
        data = service.generate_balance_sheet(as_of)
        columns = ["Account Code", "Account Name", "Category", "Amount"]
        flat_rows = []
        for entry in data.get("lines", []):
            flat_rows.append(
                [
                    entry.get("account_code"),
                    entry.get("account_name"),
                    entry.get("category") or entry.get("line_type"),
                    entry.get("amount"),
                ]
            )
        data["columns"] = columns
        data["flat_rows"] = flat_rows
        data.setdefault("filters", {})
        data["filters"].update({"as_of_date": as_of})
        data["title"] = data.get("name") or "Balance Sheet"
        return data

    # ------------------------------------------------------------------
    # Lightweight query builder path (whitelisted models/fields)

    def _query_builder_context(self, qb: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a constrained query-builder definition into rows/columns."""
        model = (qb or {}).get("model")
        fields = qb.get("fields") or []
        filters = qb.get("filters") or {}
        limit = qb.get("limit") or params.get("limit")

        allowed_models = {
            "journal": (Journal, {"journal_number", "journal_date", "status", "total_debit", "total_credit", "description"}),
            "journalline": (JournalLine, {"line_number", "debit_amount", "credit_amount", "description", "account_id"}),
        }
        if model not in allowed_models:
            return {"rows": [], "columns": [], "flat_rows": [], "filters": filters, "title": "Custom Report"}

        model_cls, allowed_fields = allowed_models[model]
        selected_fields = [f for f in fields if f in allowed_fields] or list(allowed_fields)

        qs = model_cls.objects.filter(organization=self.organization)
        if filters:
            if "start_date" in filters and hasattr(model_cls, "journal_date"):
                start = _parse_date(filters.get("start_date"))
                if start:
                    qs = qs.filter(journal_date__gte=start)
            if "end_date" in filters and hasattr(model_cls, "journal_date"):
                end = _parse_date(filters.get("end_date"))
                if end:
                    qs = qs.filter(journal_date__lte=end)
            if "status" in filters and hasattr(model_cls, "status"):
                qs = qs.filter(status=filters["status"])

        qs = qs.values(*selected_fields)
        if limit:
            try:
                qs = qs[: int(limit)]
            except Exception:
                pass

        rows = list(qs)
        flat_rows = [list(row.values()) for row in rows]
        return {
            "rows": rows,
            "columns": selected_fields,
            "flat_rows": flat_rows,
            "filters": filters,
            "title": "Custom Report",
            "chart_data": qb.get("chart_data") or [],
        }

    # ------------------------------------------------------------------
    # Stored procedure / function support

    def _call_stored_procedure(self, name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call a stored procedure/function and return a normalized context."""
        param_values = list(params.values()) if params else []
        if self.organization:
            param_values.insert(0, self.organization.id)

        with connection.cursor() as cursor:
            cursor.callproc(name, param_values)
            columns = [col[0] for col in cursor.description] if cursor.description else []
            data = cursor.fetchall() if cursor.description else []

        rows = [dict(zip(columns, row)) for row in data] if columns else []
        return {"rows": rows, "columns": columns, "flat_rows": [list(item.values()) for item in rows]}


class ReportRenderer:
    """Resolves the correct template and renders HTML/exports."""

    def __init__(self, enable_custom: bool):
        self.enable_custom = enable_custom

    def render_html(self, definition: ReportDefinition, context: Dict[str, Any], request=None) -> str:
        engine = definition.engine
        template_source = ""
        template_obj = definition.active_template(self.enable_custom)

        if template_obj:
            engine = getattr(template_obj, "engine", engine)
            template_source = getattr(template_obj, "template_html", "") or definition.template_html
        elif definition.custom_allowed(self.enable_custom):
            template_source = definition.template_html

        if template_source:
            safe_html = sanitize_template_html(template_source)
            return render_template_string(engine, safe_html, context, request=request)

        template_name = definition.base_template_name or f"reporting/base/{definition.code}.html"
        return render_base_template(template_name, context, request=request)

    def render_export(self, definition: ReportDefinition, context: Dict[str, Any], export_format: str):
        columns = context.get("columns") or []
        rows = context.get("flat_rows") or []
        title = context.get("title") or definition.name or definition.code

        if export_format == "csv":
            buffer, filename = export_csv(columns, rows, title=title)
            return buffer, filename, "text/csv"
        if export_format == "excel":
            buffer, filename = export_excel(list(columns), [list(r) for r in rows], title=title)
            return buffer, filename, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if export_format == "pdf":
            html = self.render_html(definition, context)
            buffer, filename = export_pdf(html, title=title)
            return buffer, filename, "application/pdf"
        if export_format == "html":
            html = self.render_html(definition, context)
            buffer = io.BytesIO(html.encode("utf-8"))
            filename = f"{title.replace(' ', '_').lower()}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.html"
            return buffer, filename, "text/html"
        raise ValueError(f"Unsupported export format: {export_format}")
