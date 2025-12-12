from __future__ import annotations

from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render

from accounting.models import Journal

from .utils import DEFAULT_TOGGLES, TEMPLATE_CHOICES, normalize_template_name, get_user_print_config, save_user_print_config


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
        toggles = {key: (key in request.POST) for key in DEFAULT_TOGGLES.keys()}
        save_user_print_config(request.user, template_name, toggles)
        messages.success(request, "Print preferences saved.")
        return redirect("print_settings")

    context = {
        "config": config_data,
        "template_choices": TEMPLATE_CHOICES,
    }
    return render(request, "printing/settings.html", context)


@login_required
def print_preview(request, journal_id: int):
    """Interactive print preview (config toolbar shown only with permission)."""

    journal = get_object_or_404(Journal, pk=journal_id)
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

        toggles = {key: (key in request.POST) for key in DEFAULT_TOGGLES.keys()}
        save_user_print_config(request.user, template_name, toggles)

        if request.headers.get("HX-Request"):
            response = HttpResponse("")
            response["HX-Redirect"] = request.path
            return response

        return HttpResponseRedirect(request.path)

    tpl_override = request.GET.get("template")
    if tpl_override:
        config_data["template_name"] = normalize_template_name(tpl_override)

    template_name = normalize_template_name(config_data.get("template_name"))
    config_data["template_name"] = template_name
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
        "template_root_class": template_root_class,
        "template_path": template_path,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "imbalance": imbalance,
    }
    return render(request, "printing/preview.html", context)


@login_required
def print_page(request, journal_id: int):
    """Print-optimized page (no controls) that triggers browser print dialog."""

    journal = get_object_or_404(Journal, pk=journal_id)
    lines = journal.lines.select_related(
        "account",
        "department",
        "project",
        "cost_center",
        "tax_code",
    ).all()

    _config_obj, config_data = get_user_print_config(request.user)

    config_data["template_name"] = normalize_template_name(config_data.get("template_name"))

    tpl_override = request.GET.get("template")
    if tpl_override:
        config_data["template_name"] = normalize_template_name(tpl_override)

    template_name = normalize_template_name(config_data.get("template_name"))
    config_data["template_name"] = template_name
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
        "total_debit": total_debit,
        "total_credit": total_credit,
        "imbalance": imbalance,
    }
    return render(request, "printing/print_page.html", context)
