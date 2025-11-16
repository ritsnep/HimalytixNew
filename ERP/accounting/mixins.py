from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from usermanagement.utils import PermissionUtils


class UserOrganizationMixin:
    """Inject the active organization into queryset and form helpers."""

    def get_organization(self):
        user = getattr(self.request, "user", None)
        if user and hasattr(user, "get_active_organization"):
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
        if hasattr(form.instance, "organization") and not form.instance.organization:
            form.instance.organization = organization

        if not getattr(form.instance, "pk", None) and hasattr(form.instance, "created_by"):
            form.instance.created_by = self.request.user
        elif getattr(form.instance, "pk", None) and hasattr(form.instance, "updated_by"):
            form.instance.updated_by = self.request.user

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
