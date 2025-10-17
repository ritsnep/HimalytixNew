from django.http import HttpResponseForbidden, Http404
from utils.auth import get_user_organization
from usermanagement.utils import PermissionUtils
from accounting.models import VoucherModeConfig, Journal, JournalLine
from accounting.forms_factory import build_form
from django.forms import inlineformset_factory
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render

class UserOrganizationMixin:
    """
    Mixin to provide self.organization = request.user.organization
    and inject it into form kwargs and queryset.
    """
    def get_organization(self):
        user = getattr(self.request, "user", None)
        if user and hasattr(user, "get_active_organization"):
            org = user.get_active_organization()
            if org:
                return org
        return getattr(user, "organization", None)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        org = self.get_organization()
        if org:
            kwargs['organization'] = org
        return kwargs

    def get_queryset(self):
        qs = super().get_queryset()
        org = self.get_organization()
        if org and hasattr(qs.model, "organization_id"):
            return qs.filter(organization=org)
        return qs

class PermissionRequiredMixin(LoginRequiredMixin):
    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        # Authenticated but not permitted: show custom 403
        return render(self.request, '403.html', status=403)

    def dispatch(self, request, *args, **kwargs):
        if not hasattr(self, 'permission_required'):
            return super().dispatch(request, *args, **kwargs)

        # Superusers should have all permissions
        if request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)

        module, entity, action = self.permission_required
        org = get_user_organization(request.user)
        if not PermissionUtils.has_permission(request.user, org, module, entity, action):
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)

class VoucherConfigMixin:
    """Injects config, header_form, line_formset into get_context_data()."""
    config_pk_kwarg = "config_id"

    def get_config(self):
        config_id = self.kwargs.get(self.config_pk_kwarg) or self.request.GET.get(self.config_pk_kwarg)
        if not config_id:
            from django.http import Http404
            raise Http404("Voucher config_id is required in URL or GET params.")
        return VoucherModeConfig.objects.get(
            pk=config_id,
            organization=self.request.user.get_active_organization(),
        )

    def get_forms(self):
        cfg = self.get_config()
        ui = cfg.resolve_ui()

        HeaderForm = build_form(ui["header"], organization=self.request.user.organization, prefix="hdr", model=Journal)
        LineForm = build_form(ui["lines"],  organization=self.request.user.organization, prefix="ln", model=JournalLine)

        LineFS = inlineformset_factory(
            parent_model=Journal,
            model=JournalLine,
            form=LineForm,
            extra=1, can_delete=True,
            fields="__all__"
        )
        return HeaderForm, LineFS

    def get_context_data(self, **kw):
        # Try to call super().get_context_data if it exists, else use empty dict
        try:
            ctx = super().get_context_data(**kw)
        except AttributeError:
            ctx = {}
        HeaderForm, LineFS = self.get_forms()
        if self.request.method == "POST":
            ctx["header_form"] = HeaderForm(self.request.POST)
            ctx["lines_fs"]    = LineFS(self.request.POST)
        else:
            ctx["header_form"] = HeaderForm()
            ctx["lines_fs"]    = LineFS()
        ctx["config"] = self.get_config()
        return ctx
