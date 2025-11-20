from django.contrib.auth.mixins import AccessMixin, LoginRequiredMixin
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse
from .models import Organization

class BasePermissionMixin(AccessMixin):
    entity_code = None
    required_action = None

    def has_permission(self, request):
        # Superusers always have permission
        if request.user.is_superuser:
            return True
            
        if not self.entity_code or not self.required_action:
            return True
            
        # EntityPermission model was removed - permission check disabled
        # TODO: Implement new permission system
        return True

    def handle_no_permission(self):
        messages.error(self.request, "Please log in to access this page.")
        return redirect('dashboard')

class EntityPermissionMixin(AccessMixin):
    def has_permission(self, entity_code, required_action):
        """Check if user has permission for the given entity and action"""
        if not self.request.user.is_authenticated:
            return False
            
        # Superusers bypass all permission checks
        if self.request.user.is_superuser:
            return True
            
        # Get user's active organization
        organization = self.request.user.get_active_organization()
        if not organization:
            return False
            
        # Check if user has the required permission
        return self.request.user.has_entity_permission(
            entity_code=entity_code,
            action=required_action,
            organization=organization
        )

    def handle_no_permission(self):
        messages.error(self.request, "You don't have permission to access this page.")
        return redirect('dashboard')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)

class UserOrganizationMixin(LoginRequiredMixin):
    """Mixin to handle organization context in views."""
    
    def get_organization(self):
        """Get the active organization for the current user"""
        if not self.request.user.is_authenticated:
            return None
        return self.request.user.get_active_organization()

    @property
    def organization(self):
        """Cached access to the active organization for convenient attribute usage."""
        if not hasattr(self, "_organization_cache"):
            self._organization_cache = self.get_organization()
        return self._organization_cache
    
    def get_context_data(self, **kwargs):
        """Add organization to context."""
        context = super().get_context_data(**kwargs)
        context['organization'] = self.get_organization()
        return context 