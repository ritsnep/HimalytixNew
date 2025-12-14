from __future__ import annotations

from decimal import Decimal
import logging

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy

from accounting.models import Journal

from .models import PrintTemplate
from .forms import PrintTemplateForm
from .models_audit import PrintSettingsAuditLog

from .utils import (
    DEFAULT_TOGGLES,
    PAPER_SIZES,
    TEMPLATE_CHOICES,
    get_document_model,
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
def print_preview(request, document_type: str, doc_id: int):
    """Interactive print preview (config toolbar shown only with permission)."""

    model, template_prefix = get_document_model(document_type)
    document = get_object_or_404(model, pk=doc_id)
    _require_same_organization(request, document)
    
    # Get lines with appropriate select_related
    if document_type == 'journal':
        lines = document.lines.select_related(
            "account",
            "department",
            "project",
            "cost_center",
            "tax_code",
        ).all()
    else:
        # For purchase/sales documents
        lines = document.lines.select_related(
            "product",
            "revenue_account",
            "tax_code",
        ).all() if hasattr(document, 'lines') else []

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
                "document_type": document_type,
                "doc_id": doc_id,
                "template_name": saved.template_name,
                **(saved.config or {}),
            },
        )
        logger.info(
            "print_preview_settings_updated",
            extra={
                "user_id": getattr(request.user, "id", None),
                "username": getattr(request.user, "username", None),
                "document_type": document_type,
                "doc_id": doc_id,
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
    template_path = f"printing/{template_prefix}_{template_name}.html"

    # Compute totals
    if document_type == 'journal':
        total_debit, total_credit = _compute_totals(lines)
        imbalance = total_debit - total_credit
    else:
        total_debit = getattr(document, 'total', 0)
        total_credit = 0
        imbalance = 0

    context = {
        "document": document,
        "document_type": document_type,
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
def print_page(request, document_type: str, doc_id: int):
    """Print-optimized page (no controls) that triggers browser print dialog."""

    model, template_prefix = get_document_model(document_type)
    document = get_object_or_404(model, pk=doc_id)
    _require_same_organization(request, document)
    
    # Get lines with appropriate select_related
    if document_type == 'journal':
        lines = document.lines.select_related(
            "account",
            "department",
            "project",
            "cost_center",
            "tax_code",
        ).all()
    else:
        # For purchase/sales documents
        lines = document.lines.select_related(
            "product",
            "revenue_account",
            "tax_code",
        ).all() if hasattr(document, 'lines') else []

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
    template_path = f"printing/{template_prefix}_{template_name}.html"

    # Compute totals
    if document_type == 'journal':
        total_debit, total_credit = _compute_totals(lines)
        imbalance = total_debit - total_credit
    else:
        total_debit = getattr(document, 'total', 0)
        total_credit = 0
        imbalance = 0

    context = {
        "document": document,
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


class TemplateListView(ListView):
    model = PrintTemplate
    template_name = 'printing/template_list.html'
    context_object_name = 'templates'

    def get_queryset(self):
        return PrintTemplate.objects.filter(
            user=self.request.user,
            organization=getattr(self.request, 'organization', None)
        ).order_by('document_type', 'name')


class TemplateCreateView(CreateView):
    model = PrintTemplate
    form_class = PrintTemplateForm
    template_name = 'printing/template_form.html'
    success_url = reverse_lazy('template_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['organization'] = getattr(self.request, 'organization', None)
        return kwargs

    def form_valid(self, form):
        # Get config from POST data
        config_data = {}
        for key in DEFAULT_TOGGLES.keys():
            config_data[key] = self.request.POST.get(f'config_{key}') == 'on'
        config_data['template_name'] = self.request.POST.get('template_name', 'classic')
        config_data['paper_size'] = form.cleaned_data['paper_size']
        form.instance.config = config_data
        messages.success(self.request, f"Template '{form.instance.name}' created successfully.")
        return super().form_valid(form)


class TemplateUpdateView(UpdateView):
    model = PrintTemplate
    form_class = PrintTemplateForm
    template_name = 'printing/template_form.html'
    success_url = reverse_lazy('template_list')

    def get_queryset(self):
        return PrintTemplate.objects.filter(
            user=self.request.user,
            organization=getattr(self.request, 'organization', None)
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['organization'] = getattr(self.request, 'organization', None)
        return kwargs

    def form_valid(self, form):
        # Get config from POST data
        config_data = {}
        for key in DEFAULT_TOGGLES.keys():
            config_data[key] = self.request.POST.get(f'config_{key}') == 'on'
        config_data['template_name'] = self.request.POST.get('template_name', 'classic')
        config_data['paper_size'] = form.cleaned_data['paper_size']
        form.instance.config = config_data
        messages.success(self.request, f"Template '{form.instance.name}' updated successfully.")
        return super().form_valid(form)


class TemplateDeleteView(DeleteView):
    model = PrintTemplate
    template_name = 'printing/template_confirm_delete.html'
    success_url = reverse_lazy('template_list')

    def get_queryset(self):
        return PrintTemplate.objects.filter(
            user=self.request.user,
            organization=getattr(self.request, 'organization', None)
        )

    def delete(self, request, *args, **kwargs):
        template = self.get_object()
        messages.success(request, f"Template '{template.name}' deleted successfully.")
        return super().delete(request, *args, **kwargs)


# Function-based view wrappers for login_required
@login_required
def template_list(request):
    view = TemplateListView.as_view()
    return view(request)

@login_required
def template_create(request):
    view = TemplateCreateView.as_view()
    return view(request)

@login_required
def template_update(request, pk):
    view = TemplateUpdateView.as_view()
    return view(request, pk=pk)

@login_required
def template_delete(request, pk):
    view = TemplateDeleteView.as_view()
    return view(request, pk=pk)
