from __future__ import annotations

from decimal import Decimal
import logging

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render

from accounting.models import Journal

from .models import PrintTemplate
from .models_audit import PrintSettingsAuditLog

from .utils import (
    DEFAULT_TOGGLES,
    PAPER_SIZES,
    TEMPLATE_CHOICES,
    normalize_paper_size,
    normalize_template_name,
    get_user_print_config,
    save_user_print_config,
)

logger = logging.getLogger(__name__)


def _as_decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _compute_totals(lines) -> tuple[Decimal, Decimal]:
    total_debit = Decimal("0")
    total_credit = Decimal("0")
    for line in lines:
        total_debit += _as_decimal(getattr(line, "debit_amount", 0))
        total_credit += _as_decimal(getattr(line, "credit_amount", 0))
    return total_debit, total_credit


@login_required
def print_settings(request):
    """Per-user print preferences (template + toggles)."""

    _config_obj, config_data = get_user_print_config(request.user)

    if request.method == "POST":
        template_name = request.POST.get("template_name", config_data.get("template_name", "classic"))
        payload = {key: (key in request.POST) for key in DEFAULT_TOGGLES.keys()}
        payload["paper_size"] = request.POST.get("paper_size")
        saved = save_user_print_config(request.user, template_name, payload)

        PrintSettingsAuditLog.objects.create(
            user=request.user,
            organization_id=getattr(getattr(request, "organization", None), "id", None),
            action="settings_update",
            payload={
                "template_name": saved.template_name,
                **(saved.config or {}),
            },
        )
        messages.success(request, "Print preferences saved.")
        logger.info(
            "print_settings_updated",
            extra={
                "user_id": getattr(request.user, "id", None),
                "username": getattr(request.user, "username", None),
                "organization_id": getattr(getattr(request, "organization", None), "id", None),
            },
        )
        return redirect("print_settings")

    context = {
        "config": config_data,
        "template_choices": TEMPLATE_CHOICES,
        "paper_sizes": PAPER_SIZES,
    }
    return render(request, "printing/settings.html", context)


def _require_same_organization(request, journal: Journal) -> None:
    if getattr(request.user, "is_superuser", False):
        return

    journal_org_id = getattr(journal, "organization_id", None)
    if journal_org_id is None:
        return

    req_org = getattr(request, "organization", None)
    req_org_id = getattr(req_org, "id", None)
    if not req_org_id:
        raise PermissionDenied("Active organization required")
    if journal_org_id != req_org_id:
        raise PermissionDenied("Cross-organization access blocked")


@login_required
def print_preview(request, journal_id: int):
    """Interactive print preview (config toolbar shown only with permission)."""

    journal = get_object_or_404(Journal, pk=journal_id)
    _require_same_organization(request, journal)
    lines = journal.lines.select_related(
        "account",
        "department",
        "project",
        "cost_center",
        "tax_code",
    ).all()

    config_obj, config_data = get_user_print_config(request.user)
    selected_template = normalize_template_name(config_data.get("template_name"))
    config_data["template_name"] = selected_template

    can_edit = request.user.has_perm("printing.can_edit_print_templates")

    if request.method == "POST":
        if not can_edit:
            return HttpResponseForbidden("You do not have permission to edit print templates.")

        template_name = request.POST.get("template_name", selected_template)
        template_name = normalize_template_name(template_name)

        payload = {key: (key in request.POST) for key in DEFAULT_TOGGLES.keys()}
        payload["paper_size"] = request.POST.get("paper_size")
        saved = save_user_print_config(request.user, template_name, payload)

        PrintSettingsAuditLog.objects.create(
            user=request.user,
            organization_id=getattr(getattr(request, "organization", None), "id", None),
            action="preview_update",
            payload={
                "journal_id": getattr(journal, "pk", None),
                "template_name": saved.template_name,
                **(saved.config or {}),
            },
        )
        logger.info(
            "print_preview_settings_updated",
            extra={
                "user_id": getattr(request.user, "id", None),
                "username": getattr(request.user, "username", None),
                "journal_id": getattr(journal, "pk", None),
                "organization_id": getattr(getattr(request, "organization", None), "id", None),
            },
        )

        if request.headers.get("HX-Request"):
            response = HttpResponse("")
            response["HX-Redirect"] = request.path
            return response

        return HttpResponseRedirect(request.path)

    tpl_override = request.GET.get("template")
    if tpl_override:
        config_data["template_name"] = normalize_template_name(tpl_override)

    paper_override = request.GET.get("paper")
    if paper_override:
        config_data["paper_size"] = normalize_paper_size(paper_override)

    template_name = normalize_template_name(config_data.get("template_name"))
    config_data["template_name"] = template_name
    paper_size = normalize_paper_size(config_data.get("paper_size"))
    config_data["paper_size"] = paper_size
    template_root_class = f"template-{template_name}"
    template_path = f"printing/journal_{template_name}.html"

    total_debit, total_credit = _compute_totals(lines)
    imbalance = total_debit - total_credit

    context = {
        "journal": journal,
        "lines": lines,
        "config": config_data,
        "can_edit": can_edit,
        "template_choices": TEMPLATE_CHOICES,
        "paper_sizes": PAPER_SIZES,
        "template_root_class": template_root_class,
        "template_path": template_path,
        "paper_size": paper_size,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "imbalance": imbalance,
    }
    return render(request, "printing/preview.html", context)


@login_required
def print_page(request, journal_id: int):
    """Print-optimized page (no controls) that triggers browser print dialog."""

    journal = get_object_or_404(Journal, pk=journal_id)
    _require_same_organization(request, journal)
    lines = journal.lines.select_related(
        "account",
        "department",
        "project",
        "cost_center",
        "tax_code",
    ).all()

    document_type = 'journal'
    templates = PrintTemplate.objects.filter(
        user=request.user,
        organization=getattr(request, 'organization', None),
        document_type=document_type
    )

    selected_template = None
    auto_print = False

    if templates.count() == 1:
        selected_template = templates.first()
        config_data = selected_template.config.copy()
        paper_size = selected_template.paper_size
        auto_print = True
    elif templates.count() > 1:
        selected_template_id = request.GET.get('template_id')
        if selected_template_id:
            try:
                selected_template = templates.get(id=selected_template_id)
                config_data = selected_template.config.copy()
                paper_size = selected_template.paper_size
            except PrintTemplate.DoesNotExist:
                # Fallback to default
                _config_obj, config_data = get_user_print_config(request.user)
                paper_size = config_data.get('paper_size', 'A4')
        else:
            # Show selection, use first as preview
            selected_template = templates.first()
            config_data = selected_template.config.copy()
            paper_size = selected_template.paper_size
    else:
        # No templates, use default
        _config_obj, config_data = get_user_print_config(request.user)
        paper_size = config_data.get('paper_size', 'A4')

    # Apply overrides if any
    tpl_override = request.GET.get("template")
    if tpl_override:
        config_data["template_name"] = normalize_template_name(tpl_override)

    paper_override = request.GET.get("paper")
    if paper_override:
        paper_size = normalize_paper_size(paper_override)

    template_name = normalize_template_name(config_data.get("template_name"))
    config_data["template_name"] = template_name
    paper_size = normalize_paper_size(paper_size)
    config_data["paper_size"] = paper_size
    template_root_class = f"template-{template_name}"
    template_path = f"printing/journal_{template_name}.html"

    total_debit, total_credit = _compute_totals(lines)
    imbalance = total_debit - total_credit

    context = {
        "journal": journal,
        "lines": lines,
        "config": config_data,
        "template_root_class": template_root_class,
        "template_path": template_path,
        "paper_size": paper_size,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "imbalance": imbalance,
        "templates": templates,
        "selected_template": selected_template,
        "auto_print": auto_print,
        "template_choices": TEMPLATE_CHOICES,
        "paper_sizes": PAPER_SIZES,
    }
    return render(request, "printing/print_page.html", context)
