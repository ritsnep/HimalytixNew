import json

from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.urls import reverse

from accounting.forms_factory import VoucherFormFactory, build_form
from accounting.services.voucher_errors import VoucherProcessError
from accounting.views.generic_voucher_views import (
    ConfigVoucherCreateView,
    _compute_summary_from_formset,
    _compute_summary_from_post,
    _is_htmx,
    _line_section_title,
    _prefer_display_field,
    _resolve_idempotency_key,
    _resolve_ui_sections,
)
from usermanagement.utils import PermissionUtils

from .models import VoucherConfigMaster


@require_GET
def health_check(request):
    return JsonResponse({'status': 'ok'})


@method_decorator(login_required, name="dispatch")
class VoucherEntryView(ConfigVoucherCreateView):
    template_name = "voucher_config/entry.html"

    def _render_voucher_panel(self, request, context, *, status=200):
        if _is_htmx(request):
            return render(
                request,
                "voucher_config/partials/entry_panel.html",
                context,
                status=status,
            )
        return render(
            request,
            "voucher_config/entry.html",
            context,
            status=status,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["change_type_url"] = reverse("voucher_config:select")
        context["line_endpoint"] = reverse("voucher_config:lines_add")
        return context

    def get(self, request, *args, **kwargs):
        config = self.get_voucher_config()
        organization = self.get_organization()

        try:
            build_result = VoucherFormFactory.build(
                voucher_config=config,
                organization=organization,
            )

            if len(build_result) == 3:
                header_form_cls, line_formset_cls, additional_charges_formset_cls = build_result
            else:
                header_form_cls, line_formset_cls = build_result
                additional_charges_formset_cls = None

            header_form = self._instantiate_target(header_form_cls)
            default_lines = getattr(config, "default_lines", None)
            line_formset = self._instantiate_target(
                line_formset_cls,
                initial=default_lines if default_lines else None,
            )

            additional_charges_formset = None
            if additional_charges_formset_cls:
                additional_charges_formset = additional_charges_formset_cls(prefix="additional_charges")

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
            return self._render_voucher_panel(request, context, status=200)

        line_section_title = _line_section_title(config)
        context = self.get_context_data(
            config=config,
            header_form=header_form,
            line_formset=line_formset,
            additional_charges_formset=additional_charges_formset,
            is_create=True,
            line_section_title=line_section_title,
            idempotency_key=_resolve_idempotency_key(request),
        )
        context["summary"] = _compute_summary_from_formset(line_formset)

        return self._render_voucher_panel(request, context)

    def post(self, request, *args, **kwargs):
        config = self.get_voucher_config()
        organization = self.get_organization()
        try:
            build_result = VoucherFormFactory.build(
                voucher_config=config,
                organization=organization,
            )

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
            return self._render_voucher_panel(request, context, status=200)

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

        additional_charges_formset = None
        if additional_charges_formset_cls:
            additional_charges_formset = additional_charges_formset_cls(
                data=request.POST,
                files=request.FILES,
                prefix="additional_charges",
            )

        idempotency_key = _resolve_idempotency_key(request)
        if header_form.is_valid() and line_formset.is_valid():
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
                            "create_url": reverse("voucher_config:new", args=[config.code]),
                        }
                    else:
                        payload["voucher:state"] = "draft_saved"

                    context = self.get_context_data(
                        config=config,
                        header_form=header_form,
                        line_formset=line_formset,
                        additional_charges_formset=additional_charges_formset,
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
                    response = self._render_voucher_panel(request, context)
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
                        additional_charges_formset=additional_charges_formset,
                        is_create=True,
                        line_section_title=_line_section_title(config),
                    )
                    context["summary"] = _compute_summary_from_post(request)
                    context["alert_message"] = payload["voucher:message"]
                    context["alert_level"] = "danger"
                    response = self._render_voucher_panel(request, context, status=200)
                    response["HX-Trigger"] = json.dumps(payload)
                    return response
                messages.error(request, f"Validation Error: {exc}")
            except Exception:
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
                        additional_charges_formset=additional_charges_formset,
                        is_create=True,
                        line_section_title=_line_section_title(config),
                    )
                    context["summary"] = _compute_summary_from_post(request)
                    context["alert_message"] = payload["voucher:message"]
                    context["alert_level"] = "danger"
                    response = self._render_voucher_panel(request, context, status=500)
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
            additional_charges_formset=additional_charges_formset,
            is_create=True,
            line_section_title=line_section_title,
            idempotency_key=idempotency_key,
        )
        context["summary"] = _compute_summary_from_post(request)

        return self._render_voucher_panel(request, context, status=200)


@login_required
@require_GET
def select_voucher_type(request):
    configs = VoucherConfigMaster.objects.filter(organization=request.user.organization)
    return render(request, 'voucher_config/select.html', {'configs': configs})


@login_required
@require_GET
def lines_add(request):
    voucher_code = request.GET.get("voucher_code")
    if not voucher_code:
        return HttpResponse("voucher_code parameter is required", status=400)

    organization = request.user.organization
    config = get_object_or_404(
        VoucherConfigMaster,
        code=voucher_code,
        organization=organization,
        is_active=True,
    )

    index_value = request.GET.get("index", "0")
    try:
        line_index = max(0, int(index_value))
    except ValueError:
        line_index = 0

    ui_schema = config.resolve_ui_schema() if hasattr(config, "resolve_ui_schema") else {}
    if isinstance(ui_schema, dict) and isinstance(ui_schema.get("sections"), dict):
        ui_schema = ui_schema["sections"]
    lines_schema = ui_schema.get("lines", {}) if isinstance(ui_schema, dict) else {}

    line_model = VoucherFormFactory._get_line_model_for_voucher_config(config)
    LineFormClass = build_form(
        lines_schema,
        model=line_model,
        organization=organization,
        prefix=f"lines-{line_index}",
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

    return render(
        request,
        "voucher_config/partials/line_row.html",
        {
            "form": form,
            "index": line_index,
            "voucher_code": voucher_code,
            "line_schema": line_schema,
            "line_field_order": line_field_order,
            "line_labels": line_labels,
            "line_columns": line_columns,
        },
    )



@login_required
@require_GET
def add_line_generic(request):
    """Generic add-line endpoint (prototype) that delegates to `lines_add`.

    Accepts `voucher_code` and optional `index` query params and returns the
    same partial used by the core `lines_add` view. This provides a simple
    extension point for voucher-specific partials (e.g., PO-specific row).
    """
    # For now reuse existing implementation
    return lines_add(request)


@login_required
@require_POST
def recalc(request):
    # Calculate totals from request data
    total_debit = 0
    total_credit = 0
    # Parse lines and calculate
    return JsonResponse({'total_debit': total_debit, 'total_credit': total_credit})


@login_required
@require_POST
def validate(request):
    # Validate form data
    errors = []
    if errors:
        return render(request, 'voucher_config/partials/error_banner.html', {'errors': errors}, status=422)
    return JsonResponse({'valid': True})


@login_required
@require_POST
def save_draft(request):
    from .services.draft_service import save_draft
    code = request.POST.get('code')
    result = save_draft(code, request.POST, request.user)
    if result['success']:
        return JsonResponse({'saved': True, 'voucher_id': result['voucher_id']})
    else:
        return render(request, 'voucher_config/partials/error_banner.html', {'errors': result.get('errors', [])}, status=400)


@login_required
@require_POST
def post_voucher(request):
    from .services.posting_service import VoucherConfigOrchestrator
    # Call posting
    orchestrator = VoucherConfigOrchestrator()
    result = orchestrator.process(request.POST.get('voucher_id'), 'commit', request.user, request.POST.get('idempotency_key'))
    return JsonResponse({'posted': result})


@login_required
@require_GET
def status(request):
    # Return current step
    return JsonResponse({'current_step': 'draft'})
