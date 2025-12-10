from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.utils import timezone
import logging

from usermanagement.utils import PermissionUtils

logger = logging.getLogger(__name__)


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

    def get_context_data(self, **kwargs):
        """Ensure views have access to the current organization's default currency.

        This method intentionally calls super().get_context_data when available,
        and falls back to the provided kwargs when not. It then injects
        `default_currency` (Currency instance or None) and
        `default_currency_code` (raw currency code string) into the context.
        """
        # Try to call parent context builder if present
        try:
            context = super().get_context_data(**kwargs)
        except Exception:
            context = dict(**kwargs)

        organization = self.get_organization()
        if organization:
            # `base_currency_code` is a FK to Currency; `_id` gives raw code
            context.setdefault('default_currency', getattr(organization, 'base_currency_code', None))
            context.setdefault('default_currency_code', getattr(organization, 'base_currency_code_id', None))

        return context

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
    """
    Enhanced mixin with audit logging and better UX.

    Attributes:
        permission_required: Tuple (module, entity, action) or list of tuples
        permission_required_any: If True, user needs ANY of the permissions (OR logic)
        permission_denied_message: Custom message on permission denial
        permission_denied_url: Custom redirect URL on denial
        raise_exception: If True, raise 403 instead of redirect
    """
    permission_required = None
    permission_required_any = False  # False = AND logic, True = OR logic
    permission_denied_message = None
    permission_denied_url = None
    raise_exception = False

    def get_permission_required(self):
        """
        Return the permission(s) required.
        Can be overridden to compute permissions dynamically.
        """
        if self.permission_required is None:
            return []

        # Normalize to list of tuples
        if isinstance(self.permission_required, tuple) and len(self.permission_required) == 3:
            return [self.permission_required]
        if isinstance(self.permission_required, str):
            return [self.permission_required]
        return self.permission_required

    def has_permission(self):
        """Check if user has required permission(s)."""
        perms_required = self.get_permission_required()
        if not perms_required:
            return True

        organization = self.get_organization()
        user = self.request.user

        checks = []
        for perm in perms_required:
            if isinstance(perm, tuple) and len(perm) == 3:
                module, entity, action = perm
                checks.append(PermissionUtils.has_permission(user, organization, module, entity, action))
            else:
                # Allow direct codename strings such as "accounting_expenseentry_add"
                checks.append(PermissionUtils.has_codename(user, organization, perm))

        if self.permission_required_any:
            return any(checks)  # OR logic
        return all(checks)  # AND logic

    def handle_no_permission(self):
        """Handle permission denial."""
        user = self.request.user
        perms = self.get_permission_required()

        # Audit log
        logger.warning(
            f"Permission denied: user={user.username}, "
            f"permissions={perms}, "
            f"view={self.__class__.__name__}, "
            f"path={self.request.path}"
        )

        # Custom message
        message = self.permission_denied_message or \
                  "You don't have permission to access this page."
        messages.error(self.request, message)

        # Raise exception or redirect
        if self.raise_exception:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied(message)

        redirect_url = self.permission_denied_url or 'dashboard'
        return HttpResponseRedirect(reverse_lazy(redirect_url))

    @method_decorator(never_cache)  # Prevent caching of permission-protected pages
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        organization = self.get_organization()
        if not organization:
            messages.warning(request, "Please select an organization.")
            return HttpResponseRedirect(reverse_lazy('usermanagement:select_organization'))

        if not self.has_permission():
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


class AuditLogAccessMixin:
    """
    Mixin to enforce access control on audit log views.
    
    Requirements:
    - User must be staff (is_staff=True)
    - User must have 'can_view_audit_log' permission OR be superuser/admin
    - Non-superusers only see logs for their organization
    """
    
    def dispatch(self, request, *args, **kwargs):
        """Check permissions before dispatching request."""
        if not request.user.is_authenticated:
            raise PermissionDenied("You must be logged in to view audit logs")
        
        if not request.user.is_staff:
            raise PermissionDenied("You must be a staff member to view audit logs")
        
        # Check for audit view permission
        if not self._has_audit_permission(request.user):
            raise PermissionDenied("You do not have permission to view audit logs")
        
        return super().dispatch(request, *args, **kwargs)
    
    def _has_audit_permission(self, user):
        """
        Check if user has audit log viewing permission.
        Returns True for superusers/admins or users with explicit permission.
        """
        if user.is_superuser:
            return True
        
        # Check if user is admin
        if hasattr(user, 'role') and user.role in ['superadmin', 'admin']:
            return True
        
        # Check for explicit 'can_view_audit_log' permission
        from usermanagement.models import UserPermission
        try:
            # Try to find permission for active organization
            active_org = getattr(self.request, 'active_organization', None)
            return UserPermission.objects.filter(
                user=user,
                organization=active_org,
                permission__action='view',  # Or custom 'audit' action
            ).exists()
        except Exception:
            return False
    
    def get_queryset(self):
        """Override queryset to scope by organization for non-superusers."""
        qs = super().get_queryset()
        
        if self.request.user.is_superuser:
            return qs
        
        # Non-superusers only see their organization's logs
        active_org = getattr(self.request, 'active_organization', None)
        if active_org:
            qs = qs.filter(organization=active_org)
        
        return qs


class AuditLogExportMixin:
    """
    Mixin to control export of audit logs.
    Restricts to superusers/admins and logs the export action.
    """
    
    def export_action_allowed(self, user):
        """
        Check if user is allowed to export audit logs.
        More restrictive than viewing.
        """
        if user.is_superuser:
            return True
        
        if hasattr(user, 'role') and user.role in ['superadmin', 'admin']:
            return True
        
        return False
    
    def log_export_action(self, user, count, export_format):
        """
        Log the audit log export action itself for compliance.
        """
        from accounting.models import AuditLog
        from accounting.utils.request import get_client_ip
        from django.contrib.contenttypes.models import ContentType
        
        active_org = getattr(self.request, 'active_organization', None)
        
        AuditLog.objects.create(
            user=user,
            organization=active_org,
            action='export',
            content_type=ContentType.objects.get_for_model(AuditLog),
            object_id=0,  # Virtual object
            changes={
                'export_format': export_format,
                'export_count': count,
                'export_time': str(timezone.now())
            },
            details=f"Exported {count} audit logs in {export_format} format",
            ip_address=get_client_ip(self.request) if self.request else None
        )


def require_audit_permission(view_func):
    """
    Decorator for function-based views to enforce audit log access control.
    
    Usage:
        @require_audit_permission
        def my_audit_view(request):
            ...
    """
    @method_decorator(staff_member_required)
    def wrapper(request, *args, **kwargs):
        user = request.user
        
        if not _has_audit_permission(user):
            raise PermissionDenied("You do not have permission to view audit logs")
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def _has_audit_permission(user):
    """Helper function to check audit permission."""
    if user.is_superuser:
        return True
    
    if hasattr(user, 'role') and user.role in ['superadmin', 'admin']:
        return True
    
    # Could add more sophisticated RBAC here
    return False


class AuditLogPermissionChecker:
    """
    Utility class for checking audit log permissions.
    Can be used in templates, views, or API endpoints.
    """
    
    @staticmethod
    def can_view(user, organization=None):
        """Check if user can view audit logs."""
        if not user.is_authenticated or not user.is_staff:
            return False
        
        if user.is_superuser:
            return True
        
        if hasattr(user, 'role') and user.role in ['superadmin', 'admin']:
            return True
        
        return False
    
    @staticmethod
    def can_export(user):
        """Check if user can export audit logs."""
        if not user.is_authenticated or not user.is_staff:
            return False
        
        # Only superusers and admins
        return user.is_superuser or (hasattr(user, 'role') and user.role in ['superadmin', 'admin'])
    
    @staticmethod
    def can_delete(user):
        """Check if user can delete audit logs."""
        # Very restrictive - only superusers for compliance/archival
        return user.is_superuser
    
    @staticmethod
    def get_accessible_organizations(user):
        """Get list of organizations user can view audit logs for."""
        if user.is_superuser:
            from usermanagement.models import Organization
            return Organization.objects.all()
        
        # Return user's organization(s)
        if hasattr(user, 'organization'):
            return [user.organization]
        
        return []
