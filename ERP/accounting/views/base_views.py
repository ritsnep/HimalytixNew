from django.contrib import messages
from django.views.generic import ListView
from django.shortcuts import redirect

from usermanagement.utils import PermissionUtils
from accounting.views.views_mixins import UserOrganizationMixin

class BaseListView(UserOrganizationMixin, ListView):
    paginate_by = 20
    permission_required = None

    def dispatch(self, request, *args, **kwargs):
        organization = self.get_organization()
        if not organization:
            messages.warning(request, "Please select an active organization to continue.")
            return redirect("select_organization")

        if not self._has_permission(request.user, organization):
            messages.error(request, "You don't have permission to access this page.")
            return redirect("dashboard")

        return super().dispatch(request, *args, **kwargs)

    def _get_permission_tuple(self):
        if self.permission_required and len(self.permission_required) == 3:
            return self.permission_required
        meta = self.model._meta
        return meta.app_label, meta.model_name, "view"

    def _has_permission(self, user, organization):
        module, entity, action = self._get_permission_tuple()
        return PermissionUtils.has_permission(user, organization, module, entity, action)

    def get_queryset(self):
        org = self.get_organization()
        if not org:
            return self.model.objects.none()
        return super().get_queryset().filter(organization=org)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        org = self.get_organization()

        if self.permission_required:
            app_label, model_name, action = self.permission_required
            context['can_add'] = PermissionUtils.has_permission(user, org, app_label, model_name, 'add')
            context['can_change'] = PermissionUtils.has_permission(user, org, app_label, model_name, 'change')
            context['can_delete'] = PermissionUtils.has_permission(user, org, app_label, model_name, 'delete')

        context['page_title'] = self.model._meta.verbose_name_plural.title()
        return context