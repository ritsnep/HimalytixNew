# Inventory/views/base_views.py
"""
Base view classes for Inventory app
Following the same pattern as accounting/views/base_views.py
"""
from django.views.generic import ListView
from usermanagement.mixins import UserOrganizationMixin
from usermanagement.utils import PermissionUtils


class BaseListView(UserOrganizationMixin, ListView):
    """
    Base list view for Inventory models
    Handles organization filtering and pagination
    """
    paginate_by = 20

    def get_queryset(self):
        """Filter queryset by organization"""
        queryset = super().get_queryset()
        organization = self.get_organization()
        if organization:
            queryset = queryset.filter(organization=organization)
        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        """Add permission context to template"""
        context = super().get_context_data(**kwargs)
        organization = self.get_organization()
        user = self.request.user

        # Add permission flags
        model_name = self.model._meta.model_name
        app_label = self.model._meta.app_label

        context['can_add'] = PermissionUtils.has_permission(
            user, organization, app_label, model_name, 'add'
        )
        context['can_change'] = PermissionUtils.has_permission(
            user, organization, app_label, model_name, 'change'
        )
        context['can_delete'] = PermissionUtils.has_permission(
            user, organization, app_label, model_name, 'delete'
        )
        context['organization'] = organization

        return context
