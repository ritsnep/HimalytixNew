from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from reporting.models import ReportDefinition, ReportTemplate, ScheduledReport
from reporting.tasks import run_scheduled_report
from reporting.services import ReportDataService, ReportRenderer
from reporting.utils import sanitize_template_html


DEFAULT_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "journal_report": {
        "name": "Journal Report",
        "description": "Detailed journal lines with totals and grouping.",
        "base_template_name": "reporting/base/journal_report.html",
        "query_name": "fn_report_journal",
    },
    "general_ledger": {
        "name": "General Ledger",
        "description": "Transactions by account with running balances.",
        "base_template_name": "reporting/base/general_ledger.html",
        "query_name": "fn_report_general_ledger",
    },
    "trial_balance": {
        "name": "Trial Balance",
        "description": "Debits and credits by account as of a date.",
        "base_template_name": "reporting/base/trial_balance.html",
        "query_name": "fn_report_trial_balance",
    },
    "profit_loss": {
        "name": "Profit & Loss",
        "description": "Income and expenses over a period.",
        "base_template_name": "reporting/base/profit_loss.html",
        "query_name": "fn_report_profit_loss",
    },
    "balance_sheet": {
        "name": "Balance Sheet",
        "description": "Assets, liabilities, equity as of a date.",
        "base_template_name": "reporting/base/balance_sheet.html",
        "query_name": "fn_report_balance_sheet",
    },
}


def _get_active_org(request):
    organization = getattr(request, "organization", None)
    if organization:
        user = getattr(request, "user", None)
        if user and hasattr(user, "set_active_organization"):
            user.set_active_organization(organization)
        return organization
    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False) and hasattr(user, "get_active_organization"):
        try:
            organization = user.get_active_organization()
            if organization and hasattr(user, "set_active_organization"):
                user.set_active_organization(organization)
            return organization
        except Exception:
            return None
    return None


def _load_template_source(template_name: str) -> str:
    path = Path(settings.BASE_DIR) / template_name
    if path.exists():
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return ""
    return ""


class ReportIndexView(LoginRequiredMixin, View):
    template_name = "reporting/report_index.html"

    def get(self, request):
        organization = _get_active_org(request)
        queryset = ReportDefinition.objects.filter(is_active=True)
        if organization:
            queryset = queryset.filter(models.Q(organization__isnull=True) | models.Q(organization=organization))
        definitions = queryset.order_by("code")
        return render(
            request,
            self.template_name,
            {
                "definitions": definitions,
                "organization": organization,
                "custom_enabled": settings.ENABLE_CUSTOM_REPORTS,
            },
        )


class ScheduledReportListView(LoginRequiredMixin, View):
    template_name = "reporting/scheduled_reports.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return HttpResponseForbidden("Only staff can manage schedules.")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        organization = _get_active_org(request)
        qs = ScheduledReport.objects.select_related("report_definition", "organization")
        if organization:
            qs = qs.filter(organization=organization)
        schedules = qs.order_by("-next_run")
        return render(
            request,
            self.template_name,
            {"schedules": schedules, "organization": organization},
        )

    def post(self, request):
        if request.POST.get("action") == "toggle":
            schedule_id = request.POST.get("id")
            try:
                schedule = ScheduledReport.objects.get(pk=schedule_id)
            except ScheduledReport.DoesNotExist:
                return HttpResponse(status=404)
            schedule.is_active = not schedule.is_active
            schedule.save(update_fields=["is_active", "updated_at"])
            messages.success(request, "Schedule updated.")
        elif request.POST.get("action") == "run_now":
            schedule_id = request.POST.get("id")
            try:
                schedule = ScheduledReport.objects.get(pk=schedule_id)
            except ScheduledReport.DoesNotExist:
                return HttpResponse(status=404)
            run_scheduled_report.delay(schedule.pk)
            messages.success(request, "Run requested.")
        return redirect(request.path)


class ReportDetailView(LoginRequiredMixin, View):
    template_name = "reporting/report_view.html"

    def _get_definition(self, code: str, organization):
        qs = ReportDefinition.objects.filter(code=code, is_active=True)
        definition = None
        if organization:
            definition = qs.filter(organization=organization).first()
        if not definition:
            definition = qs.filter(organization__isnull=True).first()

        if not definition and code in DEFAULT_DEFINITIONS:
            defaults = DEFAULT_DEFINITIONS[code]
            definition = ReportDefinition.objects.create(
                code=code,
                name=defaults.get("name", code.replace("_", " ").title()),
                description=defaults.get("description", ""),
                base_template_name=defaults.get("base_template_name", ""),
                query_name=defaults.get("query_name", ""),
                organization=organization,
                created_by=getattr(self.request, "user", None),
            )
        return definition

    def get(self, request, code: str):
        organization = _get_active_org(request)
        if not organization:
            messages.error(request, "Select an organization to view reports.")
            return redirect("usermanagement:select_organization")

        definition = self._get_definition(code, organization)
        if not definition:
            raise Http404("Report definition not found.")

        params = request.GET.copy()
        export_format = params.pop("export", [None])[0]
        params_dict = params.dict()

        data_service = ReportDataService(organization, user=request.user)
        context_payload = data_service.build_context(definition, params_dict)

        renderer = ReportRenderer(settings.ENABLE_CUSTOM_REPORTS)

        if export_format:
            try:
                buffer, filename, content_type = renderer.render_export(
                    definition, context_payload, export_format.lower()
                )
                response = HttpResponse(buffer.getvalue(), content_type=content_type)
                response["Content-Disposition"] = f'attachment; filename="{filename}"'
                return response
            except Exception as exc:  # noqa: BLE001
                return HttpResponse(f"Export failed: {exc}", status=400)

        try:
            rendered_report = renderer.render_html(definition, context_payload, request=request)
        except Exception as exc:  # noqa: BLE001
            messages.error(request, f"Unable to render report: {exc}")
            rendered_report = "<div class='alert alert-danger'>Unable to render report.</div>"

        context = {
            "definition": definition,
            "rendered_report": rendered_report,
            "organization": organization,
            "filters": context_payload.get("filters", {}),
            "custom_allowed": definition.custom_allowed(settings.ENABLE_CUSTOM_REPORTS),
            "designer_url": None,
            "export_formats": ["pdf", "excel", "csv", "html"],
        }
        qs = urlencode(params_dict)
        export_links = {}
        for fmt in context["export_formats"]:
            if qs:
                export_links[fmt] = f"{request.path}?{qs}&export={fmt}"
            else:
                export_links[fmt] = f"{request.path}?export={fmt}"
        context["export_links"] = export_links
        if request.user.is_staff:
            context["designer_url"] = request.build_absolute_uri(
                request.path.rstrip("/") + "/designer/"
            )
        return render(request, self.template_name, context)


class ReportDesignerView(LoginRequiredMixin, View):
    template_name = "reporting/designer.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return HttpResponseForbidden("Designer access is limited to staff/admins.")
        return super().dispatch(request, *args, **kwargs)

    def _starter_template(self, definition: ReportDefinition) -> str:
        if definition.template_html:
            return definition.template_html
        if definition.base_template_name:
            return _load_template_source(definition.base_template_name)
        fallback = DEFAULT_DEFINITIONS.get(definition.code, {})
        if fallback.get("base_template_name"):
            return _load_template_source(fallback["base_template_name"])
        return "<div class='p-3'>Start designing your report...</div>"

    def get(self, request, code: str):
        organization = _get_active_org(request)
        if not organization:
            messages.error(request, "Select an organization to use the designer.")
            return redirect("usermanagement:select_organization")

        definition = None
        if organization:
            definition = ReportDefinition.objects.filter(code=code, organization=organization).first()
        if not definition:
            definition = ReportDefinition.objects.filter(code=code, organization__isnull=True).first()
        if not definition:
            definition = ReportDefinition.objects.create(
                code=code,
                name=DEFAULT_DEFINITIONS.get(code, {}).get("name", code.replace("_", " ").title()),
                base_template_name=DEFAULT_DEFINITIONS.get(code, {}).get("base_template_name", ""),
                organization=organization,
                created_by=request.user,
            )

        data_service = ReportDataService(organization, user=request.user)
        sample_context = data_service.build_context(definition, {"limit": 5})
        # Keep preview lightweight and JSON serializable
        preview_rows = []
        for row in sample_context.get("rows", [])[:3]:
            preview_rows.append(
                {
                    "journal_number": row.get("journal_number"),
                    "journal_date": str(row.get("journal_date")),
                    "journal_type": row.get("journal_type"),
                    "status": row.get("status"),
                    "total_debit": float(row.get("total_debit") or 0),
                    "total_credit": float(row.get("total_credit") or 0),
                }
            )

        field_names = set()
        first_row = (sample_context.get("rows") or [{}])[0]
        for key in first_row.keys():
            if key != "lines":
                field_names.add(key)
        available_fields = ["organization", "generated_at"] + sorted(field_names) + list(sample_context.get("columns") or [])

        context = {
            "definition": definition,
            "organization": organization,
            "template_html": self._starter_template(definition),
            "template_json": definition.template_json or {},
            "available_fields": available_fields,
            "preview_rows": preview_rows,
        }
        return render(request, self.template_name, context)


@method_decorator(csrf_exempt, name="dispatch")
class ReportTemplateApiView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        code = request.GET.get("code")
        template_id = request.GET.get("template_id")
        include_gallery = request.GET.get("include_gallery")
        if not code:
            return Response({"detail": "code is required"}, status=400)
        organization = _get_active_org(request)
        definition = None
        if organization:
            definition = ReportDefinition.objects.filter(code=code, organization=organization).first()
        if not definition:
            definition = ReportDefinition.objects.filter(code=code, organization__isnull=True).first()
        if not definition:
            return Response({"detail": "Report definition not found."}, status=404)

        template_obj = None
        if template_id:
            try:
                template_obj = ReportTemplate.objects.get(pk=template_id)
            except ReportTemplate.DoesNotExist:
                return Response({"detail": "Template not found."}, status=404)
        else:
            template_obj = definition.active_template(settings.ENABLE_CUSTOM_REPORTS)

        payload = {
            "code": definition.code,
            "engine": getattr(template_obj, "engine", definition.engine),
            "template_html": getattr(template_obj, "template_html", definition.template_html),
            "template_json": getattr(template_obj, "template_json", definition.template_json),
            "is_custom_enabled": definition.is_custom_enabled,
        }
        if include_gallery:
            gallery_qs = ReportTemplate.objects.filter(definition=definition, is_gallery=True, is_active=True)
            if organization:
                gallery_qs = gallery_qs.filter(models.Q(organization__isnull=True) | models.Q(organization=organization))
            payload["gallery"] = [
                {
                    "id": t.id,
                    "name": t.name,
                    "description": t.description,
                    "engine": t.engine,
                }
                for t in gallery_qs.order_by("name")
            ]
        return Response(payload)

    def post(self, request):
        user = request.user
        if not user.is_staff:
            return Response({"detail": "Only staff can update templates."}, status=403)

        data = request.data if hasattr(request, "data") else request.POST
        code = data.get("code")
        template_html = sanitize_template_html(data.get("template_html", ""))
        template_json = data.get("template_json") or {}
        engine = data.get("engine", "django")
        is_custom_enabled = data.get("is_custom_enabled", True) in (True, "true", "1", 1, "yes")

        if not code or not template_html:
            return Response({"detail": "code and template_html are required."}, status=400)

        organization = _get_active_org(request)
        definition, _ = ReportDefinition.objects.get_or_create(
            code=code,
            organization=organization,
            defaults={
                "name": DEFAULT_DEFINITIONS.get(code, {}).get("name", code.replace("_", " ").title()),
                "base_template_name": DEFAULT_DEFINITIONS.get(code, {}).get("base_template_name", ""),
                "query_name": DEFAULT_DEFINITIONS.get(code, {}).get("query_name", ""),
                "created_by": user,
            },
        )

        latest_version = definition.templates.filter(organization=organization).order_by("-version").first()
        version = latest_version.version + 1 if latest_version else 1

        template = ReportTemplate.objects.create(
            definition=definition,
            organization=organization,
            name=f"{definition.name} v{version}",
            template_html=template_html,
            template_json=template_json,
            engine=engine,
            is_default=True,
            version=version,
            created_by=user,
            updated_by=user,
        )

        # Persist inline copy for fast rendering
        definition.template_html = template_html
        definition.template_json = template_json
        definition.engine = engine
        definition.is_custom_enabled = is_custom_enabled
        definition.save(update_fields=["template_html", "template_json", "engine", "is_custom_enabled", "updated_at"])

        return Response(
            {
                "id": template.id,
                "version": version,
                "definition": definition.code,
                "engine": engine,
                "is_custom_enabled": definition.is_custom_enabled,
            },
            status=201,
        )


class ReportSampleApiView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        code = request.GET.get("code")
        if not code:
            return Response({"detail": "code is required"}, status=400)
        organization = _get_active_org(request)
        if not organization:
            return Response({"detail": "No active organization"}, status=400)
        definition = None
        if organization:
            definition = ReportDefinition.objects.filter(code=code, organization=organization).first()
        if not definition:
            definition = ReportDefinition.objects.filter(code=code, organization__isnull=True).first()
        if not definition:
            return Response({"detail": "Report definition not found."}, status=404)

        data_service = ReportDataService(organization, user=request.user)
        context = data_service.build_context(definition, {"limit": 5})
        preview = []
        for row in context.get("rows", [])[:5]:
            if isinstance(row, dict):
                preview.append({k: str(v) for k, v in row.items() if k != "lines"})
        return Response({"rows": preview})
