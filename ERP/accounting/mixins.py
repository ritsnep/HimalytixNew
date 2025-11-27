from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from usermanagement.utils import PermissionUtils


class UserOrganizationMixin:
    """Inject the active organization into queryset and form helpers."""

    def get_user_organization(self):
        """Backward-compatible helper used across older views."""
        return self.get_organization()

    def get_organization(self):
        user = getattr(self.request, "user", None)
        if not user:
            return None

        organization = getattr(self.request, "organization", None)
        if organization is not None and hasattr(user, "set_active_organization"):
            user.set_active_organization(organization)
            return organization

        if hasattr(user, "get_active_organization"):
            org = user.get_active_organization()
            if org:
                return org
        return getattr(user, "organization", None)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        organization = self.get_organization()
        if organization:
            kwargs["organization"] = organization
        return kwargs

    def get_queryset(self):
        queryset = super().get_queryset()
        organization = self.get_organization()
        if organization and hasattr(queryset.model, "organization_id"):
            return queryset.filter(organization=organization)
        return queryset

    def form_valid(self, form):
        organization = self.get_organization()
        instance = getattr(form, "instance", None)
        if instance is not None:
            if hasattr(instance, "organization") and not instance.organization:
                instance.organization = organization

            if not getattr(instance, "pk", None) and hasattr(instance, "created_by"):
                instance.created_by = self.request.user
            elif getattr(instance, "pk", None) and hasattr(instance, "updated_by"):
                instance.updated_by = self.request.user

        return super().form_valid(form)


class PermissionRequiredMixin(LoginRequiredMixin, UserOrganizationMixin):
    """RBAC-aware mixin leveraging Module+Entity+Action permissions."""

    permission_required = None
    module_name = None
    entity_name = None
    action_name = None
    require_organization = True

    def get_permission_components(self):
        if self.permission_required:
            perm = self.permission_required
            if isinstance(perm, str):
                parts = perm.split(".")
                if len(parts) == 2 and "_" in parts[1]:
                    entity, action = parts[1].split("_", 1)
                    return parts[0], entity, action
            elif isinstance(perm, (list, tuple)) and len(perm) == 3:
                return tuple(perm)
        if self.module_name and self.entity_name and self.action_name:
            return self.module_name, self.entity_name, self.action_name
        raise AttributeError(
            "PermissionRequiredMixin needs a permission_required tuple or module/entity/action attributes."
        )

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        messages.error(self.request, "You don't have permission to access this page.")
        return HttpResponseRedirect(reverse_lazy("dashboard"))

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)

        organization = self.get_organization()
        if self.require_organization and not organization:
            messages.warning(request, "Please select an active organization to continue.")
            return HttpResponseRedirect(reverse_lazy("select_organization"))

        if request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)

        module, entity, action = self.get_permission_components()
        if not PermissionUtils.has_permission(request.user, organization, module, entity, action):
            return self.handle_no_permission()

        return super().dispatch(request, *args, **kwargs)


class AdvancedFormMixin:
    """
    Mixin to add advanced form features to any CreateView/UpdateView
    Features include: multi-tabs, bulk import, templates, keyboard shortcuts
    
    Usage:
        class MyCreateView(AdvancedFormMixin, PermissionRequiredMixin, CreateView):
            app_name = 'accounting'
            model_name = 'chart_of_accounts'
            template_name = 'components/_form_base_advanced.html'  # or inherit from it
    """
    app_name = None  # e.g., 'accounting', 'billing', 'inventory'
    model_name = None  # e.g., 'chart_of_accounts', 'invoice', 'product'
    
    def get_form_features(self):
        """Get enabled features from settings"""
        from django.conf import settings
        
        features_config = getattr(settings, 'ADVANCED_FORM_FEATURES', {})
        
        # Get app-specific configuration
        app_config = features_config.get(self.app_name, {})
        model_config = app_config.get(self.model_name, {})
        
        # Merge with global defaults
        default_config = features_config.get('default', {})
        merged_config = {**default_config, **model_config}
        
        return merged_config
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add form feature toggles
        features = self.get_form_features()
        context.update(features)
        
        # Add form metadata
        context['form_id'] = f'{self.model_name}-form'
        context['app_name'] = self.app_name
        context['model_name'] = self.model_name
        
        # Add list URL if not provided
        if 'list_url' not in context and hasattr(self, 'success_url'):
            context['list_url'] = self.success_url
        
        return context
