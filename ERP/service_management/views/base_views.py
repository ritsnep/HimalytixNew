# service_management/views/base_views.py
"""Base view classes for service_management app"""
from django.contrib import messages
from django.shortcuts import redirect
from django.views.generic import ListView

from usermanagement.mixins import UserOrganizationMixin
from usermanagement.utils import PermissionUtils


class BaseListView(UserOrganizationMixin, ListView):
    """Base list view for service_management models"""
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
        queryset = super().get_queryset()
        organization = self.get_organization()
        if organization:
            queryset = queryset.filter(organization=organization)
        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.get_organization()
        user = self.request.user
        model_name = self.model._meta.model_name
        app_label = self.model._meta.app_label

        context['can_add'] = PermissionUtils.has_permission(user, organization, app_label, model_name, 'add')
        context['can_change'] = PermissionUtils.has_permission(user, organization, app_label, model_name, 'change')
        context['can_delete'] = PermissionUtils.has_permission(user, organization, app_label, model_name, 'delete')
        context['organization'] = organization
        return context
