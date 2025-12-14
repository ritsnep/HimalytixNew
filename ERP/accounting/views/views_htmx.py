from django import forms
from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.contrib.auth.decorators import login_required

from .views_mixins import VoucherConfigMixin
from accounting.schema_loader import load_voucher_schema
from accounting.forms_factory import build_form
from accounting.models import JournalLine, VoucherModeConfig

from accounting.forms import AccountTypeForm

# Add comments for maintainability
# Ensure all views use LoginRequiredMixin and organization-aware logic where needed
# Remove any redundant or unused code

class LineRowHXView(LoginRequiredMixin, VoucherConfigMixin, View):
    def get(self, request, *args, **kwargs):
        voucher_type = request.GET.get("type")
        index = request.GET.get("index", "0")
        user_perms = {
            "can_edit": request.user.has_perm("accounting.change_journal"),
            "can_add": request.user.has_perm("accounting.add_journal"),
            "can_delete": request.user.has_perm("accounting.delete_journal"),
        }
        if voucher_type:
            schema, _, _ = load_voucher_schema(VoucherModeConfig(code=voucher_type))
            LineForm = build_form(schema["lines"], organization=request.user.get_active_organization(), prefix="line", model=JournalLine)
            LineFS = forms.formset_factory(LineForm, extra=0)
        else:
            _, LineFS = self.get_forms()
        form = LineFS().empty_form
        form.prefix = f"lines-{index}"
        return render(request, "accounting/partials/voucher_form_line_row.html", {"form": form, "user_perms": user_perms})

class ValidateVoucherHXView(LoginRequiredMixin, VoucherConfigMixin, View):
    def post(self, request, *args, **kwargs):
        HeaderForm, LineFS = self.get_forms()
        header_form = HeaderForm(request.POST)
        line_formset = LineFS(request.POST)
        valid = header_form.is_valid() and line_formset.is_valid()
        errors = {"header": header_form.errors, "lines": line_formset.errors}
        return JsonResponse({"valid": valid, "errors": errors})

class LookupHXView(LoginRequiredMixin, View):
    model_map = {
        "account": JournalLine.account.field.remote_field.model,
    }

    def get(self, request, model_name):
        q = request.GET.get("q", "")
        mdl = self.model_map.get(model_name)
        results = []
        if mdl is not None:
            qs = mdl.objects.filter(organization=request.user.get_active_organization(), account_name__icontains=q)[:10]
            results = [{"id": obj.pk, "text": str(obj)} for obj in qs]
        return JsonResponse({"results": results})

class VoucherConfigListHXView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        org = request.user.get_active_organization()
        configs = VoucherModeConfig.objects.filter(organization=org, archived_at__isnull=True)
        data = [
            {"id": c.config_id, "name": c.name, "code": c.code, "desc": c.description}
            for c in configs
        ]
        return JsonResponse({"configs": data})


class AccountTypeDependentFieldsHXView(LoginRequiredMixin, View):
    """Return the dependent AccountType fields (classification + financial categories) as an HTMX fragment.

    This keeps the source of truth server-side (AccountTypeForm dynamic choice configuration).
    """

    template_name = "accounting/htmx/account_type_dependent_fields.html"

    def get(self, request, *args, **kwargs):
        # Build a bound-ish form using current POST values if present (htmx hx-include)
        data = request.GET if request.GET else request.POST
        if request.headers.get("HX-Request") == "true":
            # HTMX includes will arrive as form-encoded; Django puts them in request.GET for hx-get.
            pass

        form = AccountTypeForm(data or None)
        # Ensure dynamic choices are configured based on current values
        form.is_valid()  # harmless; needed so cleaned_data exists in some cases; choices set in __init__ anyway
        return render(request, self.template_name, {"form": form})
