from django.http import Http404
from django.forms import inlineformset_factory
from django.shortcuts import render

from accounting.mixins import PermissionRequiredMixin, UserOrganizationMixin
from accounting.models import VoucherModeConfig, Journal, JournalLine
from accounting.forms_factory import build_form

class VoucherConfigMixin:
    """Injects config, header_form, line_formset into get_context_data()."""
    config_pk_kwarg = "config_id"

    def get_config(self):
        config_id = self.kwargs.get(self.config_pk_kwarg) or self.request.GET.get(self.config_pk_kwarg)
        if not config_id:
            raise Http404("Voucher config_id is required in URL or GET params.")
        return VoucherModeConfig.objects.get(
            pk=config_id,
            organization=self.request.user.get_active_organization(),
        )

    def get_forms(self):
        cfg = self.get_config()
        ui = cfg.resolve_ui()

        HeaderForm = build_form(
            ui["header"],
            organization=self.request.user.organization,
            prefix="hdr",
            model=Journal,
        )
        LineForm = build_form(
            ui["lines"],
            organization=self.request.user.organization,
            prefix="ln",
            model=JournalLine,
        )

        LineFS = inlineformset_factory(
            parent_model=Journal,
            model=JournalLine,
            form=LineForm,
            extra=1,
            can_delete=True,
            fields="__all__",
        )
        return HeaderForm, LineFS

    def get_context_data(self, **kw):
        try:
            ctx = super().get_context_data(**kw)
        except AttributeError:
            ctx = {}
        HeaderForm, LineFS = self.get_forms()
        if self.request.method == "POST":
            ctx["header_form"] = HeaderForm(self.request.POST)
            ctx["lines_fs"] = LineFS(self.request.POST)
        else:
            ctx["header_form"] = HeaderForm()
            ctx["lines_fs"] = LineFS()
        ctx["config"] = self.get_config()
        return ctx


class AccountsPayablePermissionMixin(PermissionRequiredMixin):
    permission_required = ('accounting', 'appayment', 'change')
