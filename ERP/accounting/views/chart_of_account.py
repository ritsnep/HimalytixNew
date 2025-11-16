from django.views.generic import ListView, UpdateView, DeleteView
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.http import HttpResponse, HttpResponseRedirect
from django.db import transaction
import logging

from accounting.mixins import PermissionRequiredMixin
from accounting.models import ChartOfAccount
from accounting.forms import ChartOfAccountForm
from utils.htmx import require_htmx

logger = logging.getLogger(__name__)

class ChartOfAccountListView(PermissionRequiredMixin, ListView):
    model = ChartOfAccount
    template_name = 'accounting/chart_of_accounts_list.html'
    context_object_name = 'accounts'
    paginate_by = None  # Show all for tree
    permission_required = ('accounting', 'chartofaccount', 'view')

    def get_queryset(self):
        organization = self.get_organization()
        if not organization:
            return ChartOfAccount.objects.none()
        return (
            ChartOfAccount.objects.filter(organization=organization)
            .select_related('parent_account', 'account_type')
            .order_by('account_code')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        accounts = list(self.get_queryset())
        tree = []
        id_map = {}
        for acc in accounts:
            acc.children = []
            acc.level = 0
            acc.indent_px = 0
            id_map[acc.account_id] = acc
        for acc in accounts:
            if acc.parent_account_id:
                parent = id_map.get(acc.parent_account_id)
                if parent:
                    acc.level = parent.level + 1
                    acc.indent_px = int(acc.level) * 20
                    parent.children.append(acc)
            else:
                acc.level = 0
                acc.indent_px = 0
                tree.append(acc)
        for acc in accounts:
            if not isinstance(acc.children, list):
                acc.children = list(acc.children)
        context['account_tree'] = tree
        context['create_url'] = reverse('accounting:chart_of_accounts_create')
        context['create_button_text'] = 'New Chart of Account'
        context['page_title'] = 'Chart of Accounts'
        context['breadcrumbs'] = [
            ('Chart of Accounts', None),
        ]
        context['level'] = 0
        return context

class ChartOfAccountListPartial(ChartOfAccountListView):
    template_name = "accounting/chart_of_accounts_list_partial.html"

    @method_decorator(require_htmx)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

class ChartOfAccountUpdateView(PermissionRequiredMixin, UpdateView):
    model = ChartOfAccount
    form_class = ChartOfAccountForm
    template_name = 'accounting/chart_of_accounts_form.html'
    success_url = reverse_lazy('accounting:chart_of_accounts_list')
    permission_required = ('accounting', 'chartofaccount', 'change')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        organization = self.get_organization()
        if organization:
            kwargs['organization'] = organization
        return kwargs

    def form_valid(self, form):
        try:
            with transaction.atomic():
                form.instance.updated_by = self.request.user
                response = super().form_valid(form)
                if self.request.headers.get('HX-Request'):
                    messages.success(self.request, "Chart of Account updated successfully.")
                    return HttpResponse(
                        '<div class="alert alert-success">Chart of Account updated successfully.</div>',
                        status=200
                    )
                messages.success(self.request, "Chart of Account updated successfully.")
                return response
        except Exception as e:
            logger.error(f"Error updating chart of account: {str(e)}")
            if self.request.headers.get('HX-Request'):
                return HttpResponse(
                    f'<div class="alert alert-danger">Error updating Chart of Account: {str(e)}</div>',
                    status=400
                )
            messages.error(self.request, f"Error updating Chart of Account: {str(e)}")
            return self.form_invalid(form)

    def form_invalid(self, form):
        if self.request.headers.get('HX-Request'):
            return HttpResponse(
                f'<div class="alert alert-danger">{" ".join([str(error) for error in form.non_field_errors()])}</div>',
                status=400
            )
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Edit Chart of Account'
        context['back_url'] = reverse('accounting:chart_of_accounts_list')
        context['breadcrumbs'] = [
            ('Chart of Accounts', reverse('accounting:chart_of_accounts_list')),
            ('Edit Chart of Account', None)
        ]
        context['form_post_url'] = reverse('accounting:chart_of_accounts_update', kwargs={'pk': self.object.pk})
        return context

    def handle_no_permission(self):
        logger.warning(f"User {self.request.user} denied permission to update ChartOfAccount {self.get_object().pk if self.get_object() else ''}")
        return super().handle_no_permission()

class ChartOfAccountDeleteView(PermissionRequiredMixin, DeleteView):
    model = ChartOfAccount
    template_name = 'accounting/chart_of_accounts_confirm_delete.html'
    success_url = reverse_lazy('accounting:chart_of_accounts_list')
    permission_required = ('accounting', 'chartofaccount', 'delete')

    def get_queryset(self):
        return ChartOfAccount.objects.filter(organization_id=self.request.user.organization.id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()
        context['form_title'] = 'Delete Chart of Account'
        context['page_title'] = 'Delete Chart of Account'
        context['breadcrumbs'] = [
            ('Chart of Accounts', reverse_lazy('accounting:chart_of_accounts_list')),
            (f'Delete: {obj.account_code} - {obj.account_name}', None)
        ]
        return context

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        if ChartOfAccount.objects.filter(parent_account_id=self.object.pk).exists():
            messages.error(request, "Cannot delete an account that has sub-accounts. Please remove or reassign its children first.")
            return HttpResponseRedirect(self.success_url)
        return super().delete(request, *args, **kwargs)
