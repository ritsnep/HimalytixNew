"""
Generic Voucher Views - Cross-module voucher creation and editing.
"""

import inspect
import uuid
import logging
import json
from typing import Dict, Any

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.forms import HiddenInput
from django.db import models
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse

from accounting.forms_factory import VoucherFormFactory
from accounting.forms_factory import build_form
from accounting.models import VoucherModeConfig, AuditLog, VoucherProcess
from voucher_config.models import VoucherConfigMaster
from accounting.views.base_voucher_view import BaseVoucherView
from accounting.services.voucher_errors import VoucherProcessError
from accounting.views.views_mixins import PermissionRequiredMixin
from usermanagement.utils import PermissionUtils

logger = logging.getLogger(__name__)


def _is_htmx(request) -> bool:
    return request.headers.get("HX-Request") == "true" or getattr(request, "htmx", False)


def _render_generic_panel(request, context, *, status=200):
    if _is_htmx(request):
        return render(
            request,
            "accounting/partials/generic_voucher_form_panel.html",
            context,
            status=status,
        )
    return render(
        request,
        "accounting/generic_dynamic_voucher_entry.html",
        context,
        status=status,
    )


def _resolve_ui_sections(config):
    ui_schema = config.resolve_ui_schema() if hasattr(config, "resolve_ui_schema") else {}
    if isinstance(ui_schema, dict) and isinstance(ui_schema.get("sections"), dict):
        ui_schema = ui_schema["sections"]
    header_schema = ui_schema.get("header", {}) if isinstance(ui_schema, dict) else {}
    line_schema = ui_schema.get("lines", {}) if isinstance(ui_schema, dict) else {}

    def _order(section):
        if isinstance(section, dict):
            order = section.get("__order__") or [k for k in section.keys() if k != "__order__"]
            return [k for k in order if k in section and k != "__order__"]
        return []

    return header_schema, line_schema, _order(header_schema), _order(line_schema)


def _default_additional_charges(config):
    charges = []
    footer_qs = getattr(config, "footer_charges", None)
    if not footer_qs:
        return charges
    try:
        footer_items = footer_qs.filter(is_active=True).order_by("display_order", "footer_charge_id")
    except Exception:
        return charges
    for charge in footer_items:
        ledger = getattr(charge, "ledger", None)
        ledger_label = None
        if ledger:
            code = getattr(ledger, "account_code", None)
            name = getattr(ledger, "account_name", None) or str(ledger)
            ledger_label = f"{code} - {name}" if code else name
        amount = None
        if getattr(charge, "calculation_type", None) == "amount":
            amount = charge.amount
        charges.append({
            "description": ledger_label or "Charge",
            "amount": amount,
            "gl_account": ledger_label or "",
            "is_taxable": False,
        })
    return charges


def _prefer_display_field(fields, name: str) -> str:
    if name in fields:
        try:
            if isinstance(fields[name].widget, HiddenInput):
                display_name = f"{name}_display"
                if display_name in fields:
                    return display_name
        except Exception:
            pass
        return name
    display_name = f"{name}_display"
    if display_name in fields:
        return display_name
    return name


def _safe_decimal(value):
    try:
        return float(value)
    except Exception:
        return 0.0


def _compute_summary_from_post(request) -> dict:
    total_forms = int(request.POST.get("lines-TOTAL_FORMS", 0) or 0)
    if total_forms == 0:
        total_forms = int(request.POST.get("form-TOTAL_FORMS", 0) or 0)
    total_lines = 0
    completed = 0
    total_debit = 0.0
    total_credit = 0.0
    total_qty = 0.0
    line_total = 0.0

    for idx in range(total_forms):
        delete_key = f"lines-{idx}-DELETE" if f"lines-{idx}-DELETE" in request.POST else f"form-{idx}-DELETE"
        if request.POST.get(delete_key) in ("on", "true", "1"):
            continue
        total_lines += 1

        def _field(name):
            key = f"lines-{idx}-{name}"
            if key in request.POST:
                return request.POST.get(key)
            return request.POST.get(f"form-{idx}-{name}")

        debit = _safe_decimal(_field("debit_amount") or _field("debit"))
        credit = _safe_decimal(_field("credit_amount") or _field("credit"))
        qty = _safe_decimal(_field("quantity") or _field("qty"))
        amount = _safe_decimal(_field("line_total") or _field("amount") or _field("total"))

        total_debit += debit
        total_credit += credit
        total_qty += qty
        line_total += amount

        # mark completed if any non-empty field present
        row_has_value = False
        for key, value in request.POST.items():
            if key.startswith(f"lines-{idx}-") and value not in (None, "", "0", "0.0"):
                row_has_value = True
                break
        if row_has_value:
            completed += 1

    incomplete = max(0, total_lines - completed)
    return {
        "total_lines": total_lines,
        "completed": completed,
        "incomplete": incomplete,
        "total_debit": f"{total_debit:.2f}",
        "total_credit": f"{total_credit:.2f}",
        "balance_diff": f"{(total_debit - total_credit):.2f}",
        "total_qty": f"{total_qty:.2f}",
        "line_total": f"{line_total:.2f}",
    }

def _compute_summary_from_formset(line_formset) -> dict:
    total_lines = 0
    completed = 0
    total_debit = 0.0
    total_credit = 0.0
    total_qty = 0.0
    line_total = 0.0

    for form in getattr(line_formset, "forms", []):
        data = {}
        if getattr(form, "is_bound", False) and hasattr(form, "cleaned_data") and form.cleaned_data:
            data = form.cleaned_data
        else:
            data = getattr(form, "initial", None) or {}
        if data.get("DELETE"):
            continue
        total_lines += 1

        debit = _safe_decimal(data.get("debit_amount") or data.get("debit"))
        credit = _safe_decimal(data.get("credit_amount") or data.get("credit"))
        qty = _safe_decimal(data.get("quantity") or data.get("qty"))
        amount = _safe_decimal(data.get("line_total") or data.get("amount") or data.get("total"))

        total_debit += debit
        total_credit += credit
        total_qty += qty
        line_total += amount

        row_has_value = False
        for key, value in data.items():
            if key == "DELETE":
                continue
            if value not in (None, "", "0", "0.0"):
                row_has_value = True
                break
        if row_has_value:
            completed += 1

    incomplete = max(0, total_lines - completed)
    return {
        "total_lines": total_lines,
        "completed": completed,
        "incomplete": incomplete,
        "total_debit": f"{total_debit:.2f}",
        "total_credit": f"{total_credit:.2f}",
        "balance_diff": f"{(total_debit - total_credit):.2f}",
        "total_qty": f"{total_qty:.2f}",
        "line_total": f"{line_total:.2f}",
    }


def _line_section_title(config) -> str:
    title = "Line Items"
    module = getattr(config, "module", "accounting") or "accounting"
    if module == "accounting" and "journal" in (getattr(config, "name", "") or "").lower():
        title = "Journal Lines"
    elif getattr(config, "affects_inventory", False):
        title = "Inventory Items"
    elif module in ("sales", "purchasing"):
        title = "Transaction Items"
    elif getattr(config, "name", "") and "receipt" in (config.name or "").lower():
        title = "Receipt Items"
    return title


def _resolve_idempotency_key(request) -> str:
    header_key = request.headers.get("Idempotency-Key") or request.headers.get("X-Idempotency-Key")
    if header_key:
        return header_key
    return request.POST.get("idempotency_key") or str(uuid.uuid4())

class GenericVoucherCreateView(PermissionRequiredMixin, BaseVoucherView):
    """
    Generic view for creating vouchers using VoucherModeConfig.
    """
    template_name = 'accounting/generic_dynamic_voucher_entry.html'
    permission_required = ('accounting', 'voucher', 'add')

    def get_voucher_config(self):
        """Get the voucher configuration by code (mode config preferred)."""
        code = self.kwargs.get('voucher_code')
        organization = self.get_organization()
        return get_object_or_404(
            VoucherModeConfig,
            code=code,
            organization=organization,
            is_active=True,
        )

    def get(self, request, *args, **kwargs) -> HttpResponse:
        """Display empty voucher form."""
        config = self.get_voucher_config()
        organization = self.get_organization()

        try:
            # Create forms using unified factory entry point
            build_result = VoucherFormFactory.build(
                voucher_config=config,
                organization=organization,
            )
            
            # Unpack - may be 2 or 3 items
            if len(build_result) == 3:
                header_form_cls, line_formset_cls, additional_charges_formset_cls = build_result
            else:
                header_form_cls, line_formset_cls = build_result
                additional_charges_formset_cls = None

            header_form = self._instantiate_target(header_form_cls)
            # VoucherModeConfig doesn't have default_lines attribute, use getattr with fallback
            default_lines = getattr(config, 'default_lines', None)
            line_formset = self._instantiate_target(
                line_formset_cls,
                initial=default_lines if default_lines else None
            )
            
            # Build additional charges formset if available
            additional_charges_formset = None
            if additional_charges_formset_cls:
                initial_charges = _default_additional_charges(config)
                if initial_charges:
                    additional_charges_formset = additional_charges_formset_cls(
                        prefix='additional_charges',
                        initial=initial_charges,
                    )
                else:
                    additional_charges_formset = additional_charges_formset_cls(prefix='additional_charges')
            
            # Build payment formset if affects_payments
            payment_formset = None
            if getattr(config, 'affects_payments', False):
                from accounting.forms.voucher_payment_forms import VoucherPaymentFormSet
                payment_formset = VoucherPaymentFormSet(prefix='payments', organization=organization)
                
        except VoucherProcessError as exc:
            context = self.get_context_data(
                config=config,
                header_form=None,
                line_formset=None,
                is_create=True,
                line_section_title=_line_section_title(config),
                alert_message=f"{exc.code}: {exc.message}",
                alert_level="danger",
            )
            return _render_generic_panel(request, context, status=200)

        # Determine line section title based on voucher type
        line_section_title = _line_section_title(config)
        
        context = self.get_context_data(
            config=config,
            header_form=header_form,
            line_formset=line_formset,
            additional_charges_formset=additional_charges_formset,
            payment_formset=payment_formset,
            is_create=True,
            line_section_title=line_section_title,
            idempotency_key=_resolve_idempotency_key(request),
        )
        context["summary"] = _compute_summary_from_formset(line_formset)

        logger.debug(f"GenericVoucherCreateView GET - Config: {config.code}")

        return _render_generic_panel(request, context)

    def summary(self, request, *args, **kwargs):
        """HTMX endpoint for real-time summary calculation."""
        lines_data = json.loads(request.POST.get('lines', '[]'))
        charges_data = json.loads(request.POST.get('charges', '[]')) if request.POST.get('charges') else None
        from accounting.services.voucher_summary_service import VoucherSummaryService
        summary = VoucherSummaryService.compute_from_lines(lines_data, charges_data)
        return JsonResponse(summary)

    def post(self, request, *args, **kwargs) -> HttpResponse:
        """Handle form submission."""
        config = self.get_voucher_config()
        organization = self.get_organization()
        try:
            build_result = VoucherFormFactory.build(
                voucher_config=config,
                organization=organization,
            )
            
            # Unpack - may be 2 or 3 items
            if len(build_result) == 3:
                header_form_cls, line_formset_cls, additional_charges_formset_cls = build_result
            else:
                header_form_cls, line_formset_cls = build_result
                additional_charges_formset_cls = None
                
        except VoucherProcessError as exc:
            context = self.get_context_data(
                config=config,
                header_form=None,
                line_formset=None,
                is_create=True,
                line_section_title=_line_section_title(config),
                alert_message=f"{exc.code}: {exc.message}",
                alert_level="danger",
            )
            return _render_generic_panel(request, context, status=200)

        header_form = self._instantiate_target(
            header_form_cls,
            data=request.POST,
            files=request.FILES,
        )
        line_formset = self._instantiate_target(
            line_formset_cls,
            data=request.POST,
            files=request.FILES,
        )
        
        # Build additional charges formset if available
        additional_charges_formset = None
        if additional_charges_formset_cls:
            additional_charges_formset = additional_charges_formset_cls(
                data=request.POST,
                files=request.FILES,
                prefix='additional_charges',
            )

        # Build payment formset if affects_payments
        payment_formset = None
        if getattr(config, 'affects_payments', False):
            from accounting.forms.voucher_payment_forms import VoucherPaymentFormSet
            payment_formset = VoucherPaymentFormSet(
                data=request.POST,
                files=request.FILES,
                prefix='payments',
                organization=organization
            )

        idempotency_key = _resolve_idempotency_key(request)
        all_valid = header_form.is_valid() and line_formset.is_valid()
        if additional_charges_formset:
            all_valid = all_valid and additional_charges_formset.is_valid()
        if payment_formset:
            all_valid = all_valid and payment_formset.is_valid()
            # Additional: validate payment sum equals voucher total
            if all_valid:
                from decimal import Decimal
                voucher_total = sum(
                    (l.get('debit_amount', 0) or 0) - (l.get('credit_amount', 0) or 0) 
                    for l in line_formset.cleaned_data if not l.get('DELETE')
                )
                payment_total = sum(
                    (p.get('amount', 0) or 0) 
                    for p in payment_formset.cleaned_data if not p.get('DELETE')
                )
                if abs(voucher_total - payment_total) > Decimal('0.01'):
                    raise VoucherProcessError('Payment total must match voucher balance.', code='PAY-BALANCE')
        
        if all_valid:
            try:
                header_data = header_form.cleaned_data
                lines_data = line_formset.cleaned_data

                action = request.POST.get("action", "save")
                if action == "submit_voucher":
                    if not PermissionUtils.has_permission(
                        request.user, organization, "accounting", "journal", "submit_journal"
                    ):
                        messages.error(request, "You do not have permission to submit vouchers.")
                        action = "save"
                if action == "post_voucher":
                    if not PermissionUtils.has_permission(
                        request.user, organization, "accounting", "journal", "post_journal"
                    ):
                        messages.error(request, "You do not have permission to post vouchers.")
                        action = "save"
                if action == "post_voucher":
                    commit_type = "post"
                elif action == "submit_voucher":
                    commit_type = "submit"
                else:
                    commit_type = "save"

                from accounting.services.voucher_orchestrator import VoucherOrchestrator
                # Check concurrency
                modified_at = request.POST.get('modified_at')
                if modified_at:
                    from accounting.models import Voucher  # Assuming Voucher model
                    existing_voucher = Voucher.objects.filter(
                        organization=organization, 
                        voucher_type=config.code, 
                        modified_at__gt=modified_at
                    ).first()
                    if existing_voucher:
                        return _render_generic_panel(request, {
                            'config': config,
                            'alert_message': 'Voucher modified by another user.',
                            'alert_level': 'danger'
                        }, status=409)
                
                voucher = VoucherOrchestrator(request.user).create_and_process(
                    config=config,
                    header_data=header_data,
                    lines_data=lines_data,
                    action=action,
                    idempotency_key=idempotency_key,
                )

                voucher_number = (
                    getattr(voucher, "voucher_number", None)
                    or getattr(voucher, "journal_number", None)
                    or voucher.pk
                )
                messages.success(request, f"Voucher {voucher_number} saved successfully.")
                detail_url = reverse("accounting:voucher_detail", args=[voucher.pk])
                if _is_htmx(request):
                    payload = {
                        "voucher:save": "done",
                        "voucher:journal": "done",
                        "voucher:post": "done" if commit_type == "post" else "pending",
                        "voucher:inventory": "done" if commit_type == "post" else "pending",
                        "voucher:complete": "done",
                        "voucher:message": "Voucher saved successfully.",
                    }
                    if commit_type == "submit":
                        payload["voucher:post"] = "pending"
                        payload["voucher:inventory"] = "pending"
                        payload["voucher:complete"] = "done"
                        payload["voucher:message"] = "Voucher submitted for approval."
                        payload["voucher:state"] = "submitted"
                    elif commit_type == "post":
                        payload["voucher:state"] = "posted"
                        payload["voucher:post_success"] = {
                            "detail_url": detail_url,
                            "create_url": reverse("accounting:generic_voucher_create", args=[config.code]),
                        }
                    else:
                        payload["voucher:state"] = "draft_saved"
                    context = self.get_context_data(
                        config=config,
                        header_form=header_form,
                        line_formset=line_formset,
                        is_create=True,
                        line_section_title=_line_section_title(config),
                        idempotency_key=idempotency_key,
                    )
                    context["summary"] = _compute_summary_from_post(request)
                    context["voucher_status"] = getattr(voucher, "status", None)
                    context["draft_saved"] = commit_type == "save"
                    if commit_type == "post":
                        context["voucher_id"] = voucher.pk
                        context["process_attempt"] = getattr(voucher, "process_attempt", None)
                    context["alert_message"] = payload["voucher:message"]
                    context["alert_level"] = "success"
                    response = _render_generic_panel(request, context)
                    response["HX-Trigger"] = json.dumps(payload)
                    return response
                return redirect(detail_url)

            except VoucherProcessError as exc:
                error_message = f"{exc.code}: {exc.message}"
                if _is_htmx(request):
                    step = "save"
                    if exc.code.startswith("INV"):
                        step = "inventory"
                    elif exc.code.startswith("GL"):
                        step = "post"
                    step_label = {
                        "save": "Voucher Save",
                        "post": "Posting to GL",
                        "inventory": "Inventory Update",
                    }.get(step, "Processing")
                    journal_state = "done" if step in ("post", "inventory") else "fail"
                    payload = {
                        "voucher:save": "done" if step != "save" else "fail",
                        "voucher:journal": journal_state,
                        "voucher:post": "fail" if step == "post" else "pending",
                        "voucher:inventory": "fail" if step == "inventory" else "pending",
                        "voucher:complete": "fail",
                        "voucher:error_code": exc.code,
                        "voucher:message": f"{step_label}: {error_message}",
                    }
                    context = self.get_context_data(
                        config=config,
                        header_form=header_form,
                        line_formset=line_formset,
                        is_create=True,
                        line_section_title=_line_section_title(config),
                    )
                    context["summary"] = _compute_summary_from_post(request)
                    context["alert_message"] = payload["voucher:message"]
                    context["alert_level"] = "danger"
                    response = _render_generic_panel(request, context, status=200)
                    response["HX-Trigger"] = json.dumps(payload)
                    return response
                messages.error(request, f"Validation Error: {error_message}")
            except ValidationError as exc:
                if _is_htmx(request):
                    message = str(exc)
                    step = "save"
                    message_lower = message.lower()
                    if "inventory" in message_lower or "stock" in message_lower:
                        step = "inventory"
                    elif "ledger" in message_lower or "gl" in message_lower:
                        step = "post"
                    elif commit_type == "post":
                        step = "post"
                    step_label = {
                        "save": "Voucher Save",
                        "post": "Posting to GL",
                        "inventory": "Inventory Update",
                    }.get(step, "Processing")
                    journal_state = "done" if step in ("post", "inventory") else "fail"
                    payload = {
                        "voucher:save": "done" if step != "save" else "fail",
                        "voucher:journal": journal_state,
                        "voucher:post": "fail" if step == "post" else "pending",
                        "voucher:inventory": "fail" if step == "inventory" else "pending",
                        "voucher:complete": "fail",
                        "voucher:message": f"{step_label}: {message}",
                    }
                    context = self.get_context_data(
                        config=config,
                        header_form=header_form,
                        line_formset=line_formset,
                        is_create=True,
                        line_section_title=_line_section_title(config),
                    )
                    context["summary"] = _compute_summary_from_post(request)
                    context["alert_message"] = payload["voucher:message"]
                    context["alert_level"] = "danger"
                    response = _render_generic_panel(request, context, status=200)
                    response["HX-Trigger"] = json.dumps(payload)
                    return response
                messages.error(request, f"Validation Error: {exc}")
            except Exception:
                logger.exception("Critical Voucher Save Error")
                if _is_htmx(request):
                    payload = {
                        "voucher:save": "fail",
                        "voucher:journal": "fail",
                        "voucher:post": "pending",
                        "voucher:inventory": "pending",
                        "voucher:complete": "fail",
                        "voucher:message": "A system error occurred. The transaction has been rolled back.",
                    }
                    context = self.get_context_data(
                        config=config,
                        header_form=header_form,
                        line_formset=line_formset,
                        is_create=True,
                        line_section_title=_line_section_title(config),
                    )
                    context["summary"] = _compute_summary_from_post(request)
                    context["alert_message"] = payload["voucher:message"]
                    context["alert_level"] = "danger"
                    # Return 200 so HTMX will swap the returned panel and show the error UI
                    response = _render_generic_panel(request, context, status=200)
                    response["HX-Trigger"] = json.dumps(payload)
                    return response
                messages.error(
                    request,
                    "A system error occurred. The transaction has been rolled back.",
                )
        else:
            messages.error(request, "Please correct the errors in the form.")

        line_section_title = _line_section_title(config)

        context = self.get_context_data(
            config=config,
            header_form=header_form,
            line_formset=line_formset,
            is_create=True,
            line_section_title=line_section_title,
            idempotency_key=idempotency_key,
        )
        context["summary"] = _compute_summary_from_post(request)

        return _render_generic_panel(request, context, status=200)

    def get_success_url(self, voucher):
        """Return URL to redirect after successful creation."""
        # This should be configurable based on the voucher type
        return reverse('accounting:voucher_list')

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        """Build context for template."""
        context = super().get_context_data(**kwargs)
        organization = self.get_organization()
        user = getattr(self, "request", None).user if hasattr(self, "request") else None
        can_submit = False
        can_post = False
        if user and organization:
            can_submit = PermissionUtils.has_permission(user, organization, "accounting", "journal", "submit_journal")
            can_post = PermissionUtils.has_permission(user, organization, "accounting", "journal", "post_journal")
        config = kwargs.get("config")
        header_schema = {}
        line_schema = {}
        header_order = []
        line_order = []
        if config:
            header_schema, line_schema, header_order, line_order = _resolve_ui_sections(config)
        line_labels = {}
        if isinstance(line_schema, dict):
            for key, cfg in line_schema.items():
                if key == "__order__":
                    continue
                if isinstance(cfg, dict):
                    line_labels[key] = cfg.get("label") or key.replace("_", " ").title()
                else:
                    line_labels[key] = str(key)

        header_form = kwargs.get("header_form")
        line_formset = kwargs.get("line_formset")
        header_fields = []
        if header_form and header_order:
            for name in header_order:
                mapped = _prefer_display_field(header_form.fields, name)
                if mapped in header_form.fields:
                    header_fields.append(header_form[mapped])
        elif header_form:
            header_fields = list(header_form.visible_fields())

        line_field_order = []
        if line_formset and line_order:
            for name in line_order:
                mapped = _prefer_display_field(line_formset.form.base_fields, name)
                if mapped in line_formset.form.base_fields:
                    line_field_order.append(mapped)
        elif line_formset:
            line_field_order = list(line_formset.form.base_fields.keys())
        line_columns = []
        for name in line_order:
            mapped = _prefer_display_field(line_formset.form.base_fields, name) if line_formset else name
            if line_formset and mapped not in line_formset.form.base_fields:
                continue
            line_columns.append({
                "name": mapped,
                "label": line_labels.get(name, name),
            })
        if not line_columns and line_field_order:
            line_columns = [{"name": name, "label": line_labels.get(name, name)} for name in line_field_order]
        context.update({
            'page_title': f"Create {kwargs.get('config').name}",
            'voucher_type': kwargs.get('config').code,
            'can_submit': can_submit,
            'can_post': can_post,
            'can_approve': PermissionUtils.has_permission(user, organization, "accounting", "journal", "approve_journal") if user and organization else False,
            'journal_type_name': getattr(getattr(kwargs.get('config'), 'journal_type', None), 'name', None),
            'voucher_status': kwargs.get('voucher_status'),
            'line_endpoint': reverse('accounting:generic_voucher_line'),
            'change_type_url': reverse('accounting:generic_voucher_select'),
            'header_schema': header_schema,
            'line_schema': line_schema,
            'header_fields': header_fields,
            'line_field_order': line_field_order,
            'line_labels': line_labels,
            'line_columns': line_columns,
        })
        return context

    @staticmethod
    def _instantiate_target(target, data=None, files=None, **extra):
        """Helper that instantiates form/formset classes when needed."""
        if inspect.isclass(target):
            init_kwargs = {}
            if data is not None:
                init_kwargs['data'] = data
            if files is not None:
                init_kwargs['files'] = files
            for key, value in extra.items():
                if value is not None:
                    init_kwargs[key] = value
            return target(**init_kwargs)
        return target


class GenericVoucherLineView(PermissionRequiredMixin, BaseVoucherView):
    """HTMX endpoint that renders an additional line item for the generic voucher form."""

    permission_required = ('accounting', 'voucher', 'add')

    def get(self, request, *args, **kwargs) -> HttpResponse:
        voucher_code = request.GET.get('voucher_code')
        if not voucher_code:
            return HttpResponse("voucher_code parameter is required", status=400)

        organization = self.get_organization()
        config = get_object_or_404(
            VoucherModeConfig,
            code=voucher_code,
            organization=organization,
            is_active=True
        )

        index_value = request.GET.get('index', '0')
        try:
            line_index = max(0, int(index_value))
        except ValueError:
            line_index = 0

        ui_schema = config.resolve_ui_schema() if hasattr(config, 'resolve_ui_schema') else {}
        if isinstance(ui_schema, dict) and isinstance(ui_schema.get('sections'), dict):
            ui_schema = ui_schema['sections']
        lines_schema = ui_schema.get('lines', {}) if isinstance(ui_schema, dict) else {}
        line_model = VoucherFormFactory._get_line_model_for_voucher_config(config)
        LineFormClass = build_form(
            lines_schema,
            model=line_model,
            organization=organization,
            prefix=f"lines-{line_index}"
        )

        form = LineFormClass()
        _, line_schema, _, line_order = _resolve_ui_sections(config)
        line_field_order = []
        for name in line_order:
            mapped = _prefer_display_field(LineFormClass.base_fields, name)
            if mapped in LineFormClass.base_fields:
                line_field_order.append(mapped)
        if not line_field_order:
            line_field_order = list(LineFormClass.base_fields.keys())
        line_labels = {}
        if isinstance(line_schema, dict):
            for key, cfg in line_schema.items():
                if key == "__order__":
                    continue
                if isinstance(cfg, dict):
                    line_labels[key] = cfg.get("label") or key.replace("_", " ").title()
                else:
                    line_labels[key] = str(key)
        line_columns = []
        for name in line_order:
            mapped = _prefer_display_field(LineFormClass.base_fields, name)
            if mapped in LineFormClass.base_fields:
                line_columns.append({"name": mapped, "label": line_labels.get(name, name)})
        if not line_columns:
            line_columns = [{"name": name, "label": line_labels.get(name, name)} for name in line_field_order]

        return render(request, 'accounting/partials/generic_dynamic_voucher_line_row.html', {
            'form': form,
            'index': line_index,
            'line_schema': line_schema,
            'line_field_order': line_field_order,
            'line_labels': line_labels,
            'line_columns': line_columns,
        })


class ConfigVoucherCreateView(GenericVoucherCreateView):
    """Generic view for creating vouchers using VoucherConfigMaster."""

    def get_voucher_config(self):
        code = self.kwargs.get('voucher_code')
        organization = self.get_organization()
        return get_object_or_404(
            VoucherConfigMaster,
            code=code,
            organization=organization,
            is_active=True,
        )

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update({
            'line_endpoint': reverse('accounting:config_voucher_line'),
            'change_type_url': reverse('accounting:generic_voucher_select'),
        })
        return context


class ConfigVoucherLineView(PermissionRequiredMixin, BaseVoucherView):
    """HTMX endpoint that renders an additional line item for config-driven vouchers."""

    permission_required = ('accounting', 'voucher', 'add')

    def get(self, request, *args, **kwargs) -> HttpResponse:
        voucher_code = request.GET.get('voucher_code')
        if not voucher_code:
            return HttpResponse("voucher_code parameter is required", status=400)

        organization = self.get_organization()
        config = get_object_or_404(
            VoucherConfigMaster,
            code=voucher_code,
            organization=organization,
            is_active=True,
        )

        index_value = request.GET.get('index', '0')
        try:
            line_index = max(0, int(index_value))
        except ValueError:
            line_index = 0

        ui_schema = config.resolve_ui_schema() if hasattr(config, 'resolve_ui_schema') else {}
        if isinstance(ui_schema, dict) and isinstance(ui_schema.get('sections'), dict):
            ui_schema = ui_schema['sections']
        lines_schema = ui_schema.get('lines', {}) if isinstance(ui_schema, dict) else {}
        line_model = VoucherFormFactory._get_line_model_for_voucher_config(config)
        LineFormClass = build_form(
            lines_schema,
            model=line_model,
            organization=organization,
            prefix=f"lines-{line_index}"
        )

        form = LineFormClass()
        _, line_schema, _, line_order = _resolve_ui_sections(config)
        line_field_order = []
        for name in line_order:
            mapped = _prefer_display_field(LineFormClass.base_fields, name)
            if mapped in LineFormClass.base_fields:
                line_field_order.append(mapped)
        if not line_field_order:
            line_field_order = list(LineFormClass.base_fields.keys())
        line_labels = {}
        if isinstance(line_schema, dict):
            for key, cfg in line_schema.items():
                if key == "__order__":
                    continue
                if isinstance(cfg, dict):
                    line_labels[key] = cfg.get("label") or key.replace("_", " ").title()
                else:
                    line_labels[key] = str(key)
        line_columns = []
        for name in line_order:
            mapped = _prefer_display_field(LineFormClass.base_fields, name)
            if mapped in LineFormClass.base_fields:
                line_columns.append({"name": mapped, "label": line_labels.get(name, name)})
        if not line_columns:
            line_columns = [{"name": name, "label": line_labels.get(name, name)} for name in line_field_order]

        return render(request, 'accounting/partials/generic_dynamic_voucher_line_row.html', {
            'form': form,
            'index': line_index,
            'line_schema': line_schema,
            'line_field_order': line_field_order,
            'line_labels': line_labels,
            'line_columns': line_columns,
        })


class VoucherTypeSelectionView(PermissionRequiredMixin, BaseVoucherView):
    """
    View for selecting voucher type before creation.
    """
    template_name = 'accounting/voucher_type_selection.html'
    permission_required = ('accounting', 'voucher', 'add')

    def get(self, request, *args, **kwargs) -> HttpResponse:
        """Display voucher type selection."""
        organization = self.get_organization()

        # Get all active voucher configurations
        if organization is None:
            configs = VoucherModeConfig.objects.none()
        else:
            configs = VoucherModeConfig.objects.filter(
                organization=organization,
                is_active=True,
            ).exclude(
                schema_definition__isnull=True,
            ).order_by('code')

        configs_by_module = {}
        for cfg in configs:
            module = getattr(cfg, "module", "accounting") or "accounting"
            label = module.replace("_", " ").title()
            configs_by_module.setdefault(label, []).append(cfg)

        context = self.get_context_data(configs=configs, configs_by_module=configs_by_module)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        """Build context."""
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': 'Select Voucher Type',
            'configs': kwargs.get('configs', []),
        })
        return context


class GenericVoucherRecalcView(PermissionRequiredMixin, BaseVoucherView):
    """HTMX endpoint to recompute summary totals from posted form data."""

    permission_required = ('accounting', 'voucher', 'add')

    def post(self, request, *args, **kwargs) -> HttpResponse:
        summary = _compute_summary_from_post(request)
        return render(
            request,
            "accounting/partials/generic_voucher_summary.html",
            {"summary": summary},
        )


class GenericVoucherValidateView(PermissionRequiredMixin, BaseVoucherView):
    """HTMX endpoint to validate voucher input without saving."""

    permission_required = ("accounting", "voucher", "add")

    def post(self, request, *args, **kwargs) -> HttpResponse:
        config = get_object_or_404(
            VoucherModeConfig,
            code=kwargs.get("voucher_code"),
            organization=self.get_organization(),
            is_active=True,
        )
        organization = self.get_organization()
        try:
            header_form_cls, line_formset_cls = VoucherFormFactory.build(
                voucher_config=config,
                organization=organization,
            )
        except VoucherProcessError as exc:
            context = self.get_context_data(
                config=config,
                header_form=None,
                line_formset=None,
                is_create=True,
                line_section_title=_line_section_title(config),
                alert_message=f"{exc.code}: {exc.message}",
                alert_level="danger",
                idempotency_key=_resolve_idempotency_key(request),
            )
            return _render_generic_panel(request, context, status=200)

        header_form = self._instantiate_target(header_form_cls, data=request.POST, files=request.FILES)
        line_formset = self._instantiate_target(line_formset_cls, data=request.POST, files=request.FILES)

        context = self.get_context_data(
            config=config,
            header_form=header_form,
            line_formset=line_formset,
            is_create=True,
            line_section_title=_line_section_title(config),
            idempotency_key=_resolve_idempotency_key(request),
        )
        status = 200 if header_form.is_valid() and line_formset.is_valid() else 422
        if status == 200:
            context["alert_message"] = "Validation passed."
            context["alert_level"] = "success"
        return _render_generic_panel(request, context, status=status)


class VoucherProcessStatusView(PermissionRequiredMixin, BaseVoucherView):
    """HTMX endpoint to poll current voucher process state."""

    permission_required = ("accounting", "voucher", "view")

    def get(self, request, *args, **kwargs) -> HttpResponse:
        voucher_id = kwargs.get("voucher_id")
        organization = self.get_organization()
        process = None
        if voucher_id and organization:
            process = (
                VoucherProcess.objects.filter(organization=organization)
                .filter(models.Q(journal_id=voucher_id) | models.Q(journal_id_snapshot=voucher_id))
                .order_by("-started_at")
                .first()
            )
        context = {"process_attempt": process, "voucher_id": voucher_id}
        return render(request, "accounting/partials/voucher_process_tracker.html", context)
