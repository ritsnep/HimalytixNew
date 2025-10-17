from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from usermanagement.utils import PermissionUtils
class UserOrganizationMixin:
    """
    Mixin to provide access to user's organization and inject it into
    form kwargs and queryset.
    """
    def get_organization(self):
        # First try get_active_organization() method
        if hasattr(self.request.user, 'get_active_organization'):
            org = self.request.user.get_active_organization()
            if org:
                return org
        
        # Fall back to organization property
        return getattr(self.request.user, "organization", None)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        org = self.get_organization()
        if org:
            kwargs['organization'] = org
        return kwargs

    def get_queryset(self):
        org = self.get_organization()
        qs = super().get_queryset()
        if org and hasattr(qs.model, "organization_id"):
            return qs.filter(organization=org)
        return qs
        
    def form_valid(self, form):
        # Set organization on the instance if it has an organization field
        if hasattr(form.instance, 'organization') and not form.instance.organization:
            form.instance.organization = self.get_organization()
        
        # Set created_by or updated_by if applicable
        if not getattr(form.instance, 'pk', None) and hasattr(form.instance, 'created_by'):
            form.instance.created_by = self.request.user
        elif getattr(form.instance, 'pk', None) and hasattr(form.instance, 'updated_by'):
            form.instance.updated_by = self.request.user
            
        return super().form_valid(form)
class PermissionRequiredMixin(LoginRequiredMixin):
    """
    Mixin that checks if the user has permission to access the view
    """
    module_name = None
    entity_name = None
    action_name = None

    def dispatch(self, request, *args, **kwargs):
        # First run the LoginRequiredMixin's dispatch
        login_result = super(LoginRequiredMixin, self).dispatch(request, *args, **kwargs)
        if login_result.status_code != 200:
            return login_result

        organization = self.get_organization()
        if not organization:
            messages.warning(request, "Please select an active organization to continue.")
            return HttpResponseRedirect(reverse_lazy('select_organization'))

        if not PermissionUtils.has_permission(
            request.user,
            organization,
            self.module_name,
            self.entity_name,
            self.action_name
        ):
            messages.error(request, "You don't have permission to access this page.")
            return HttpResponseRedirect(reverse_lazy('dashboard'))

        return super().dispatch(request, *args, **kwargs)

    def get_organization(self):
        # First try get_active_organization() method
        if hasattr(self.request.user, 'get_active_organization'):
            return self.request.user.get_active_organization()
        # Fall back to organization property
        return getattr(self.request.user, "organization", None)
