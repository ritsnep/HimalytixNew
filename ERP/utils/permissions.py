"""
Permissions & Security Utilities

Provides centralized permission checking, role-based access control,
and security validation for the accounting system.
"""

from typing import Optional, Dict, List, Any, Tuple, Union, Set
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.core.exceptions import PermissionDenied

from .organization import OrganizationService


class PermissionChecker:
    """
    Centralized service for checking user permissions across the application.
    """

    # Permission constants
    VIEW = 'view'
    ADD = 'add'
    CHANGE = 'change'
    DELETE = 'delete'

    # Custom accounting permissions
    APPROVE_JOURNAL = 'accounting.approve_journal'
    POST_JOURNAL = 'accounting.post_journal'
    REVERSE_JOURNAL = 'accounting.reverse_journal'
    VIEW_ALL_ORGS = 'accounting.view_all_organizations'
    MANAGE_FISCAL_YEAR = 'accounting.manage_fiscal_year'
    EXPORT_DATA = 'accounting.export_data'

    @staticmethod
    def has_model_permission(
        user: User,
        model: models.Model,
        action: str,
        organization: Optional[Any] = None
    ) -> bool:
        """
        Check if user has permission for a specific model and action.

        Args:
            user: User instance
            model: Django model class or instance
            action: Permission action ('view', 'add', 'change', 'delete')
            organization: Organization context (optional)

        Returns:
            True if user has permission, False otherwise

        Usage:
            # Check if user can edit journals
            if PermissionChecker.has_model_permission(request.user, Journal, 'change'):
                # Allow edit
        """
        if not user or not user.is_authenticated:
            return False

        # Superusers have all permissions
        if user.is_superuser:
            return True

        # Get model class
        if isinstance(model, models.Model):
            model_class = model.__class__
        else:
            model_class = model

        # Build permission codename
        app_label = model_class._meta.app_label
        model_name = model_class._meta.model_name
        codename = f"{action}_{model_name}"

        # Check Django permissions
        if user.has_perm(f"{app_label}.{codename}"):
            return True

        # Check organization-specific permissions
        if organization:
            return PermissionChecker._has_org_specific_permission(
                user, app_label, codename, organization
            )

        return False

    @staticmethod
    def has_field_permission(
        user: User,
        model: models.Model,
        field_name: str,
        action: str,
        organization: Optional[Any] = None
    ) -> bool:
        """
        Check if user has permission to access a specific field.

        Args:
            user: User instance
            model: Model instance
            field_name: Name of the field
            action: Permission action
            organization: Organization context

        Returns:
            True if user has field permission

        Usage:
            # Check if user can view sensitive financial data
            if PermissionChecker.has_field_permission(user, account, 'balance', 'view'):
                # Show balance
        """
        # First check model permission
        if not PermissionChecker.has_model_permission(user, model, action, organization):
            return False

        # Check field-specific restrictions
        field_restrictions = PermissionChecker._get_field_restrictions(user, organization)

        # Check if field is restricted
        restricted_fields = field_restrictions.get('restricted_fields', [])
        if field_name in restricted_fields:
            return False

        # Check if field requires special permission
        special_permissions = field_restrictions.get('special_permissions', {})
        required_perm = special_permissions.get(field_name)
        if required_perm:
            return user.has_perm(required_perm)

        return True

    @staticmethod
    def has_accounting_permission(
        user: User,
        permission: str,
        organization: Optional[Any] = None
    ) -> bool:
        """
        Check accounting-specific permissions.

        Args:
            user: User instance
            permission: Permission codename
            organization: Organization context

        Returns:
            True if user has the permission

        Usage:
            # Check if user can approve journals
            if PermissionChecker.has_accounting_permission(
                request.user, PermissionChecker.APPROVE_JOURNAL
            ):
                # Show approve button
        """
        if not user or not user.is_authenticated:
            return False

        if user.is_superuser:
            return True

        # Check direct permission
        if user.has_perm(permission):
            return True

        # Check organization-specific permissions
        if organization:
            return PermissionChecker._has_org_specific_permission(
                user, *permission.split('.'), organization
            )

        return False

    @staticmethod
    def can_access_organization(user: User, organization: Any) -> bool:
        """
        Check if user can access a specific organization.

        Args:
            user: User instance
            organization: Organization instance

        Returns:
            True if user has access

        Usage:
            # Before showing org-specific data
            if not PermissionChecker.can_access_organization(request.user, target_org):
                raise PermissionDenied()
        """
        return OrganizationService.validate_org_access(user, organization)

    @staticmethod
    def get_user_permissions(user: User, organization: Optional[Any] = None) -> Dict[str, List[str]]:
        """
        Get all permissions for a user, optionally filtered by organization.

        Args:
            user: User instance
            organization: Organization filter (optional)

        Returns:
            Dictionary of permissions by category

        Usage:
            # Get user permissions for UI rendering
            perms = PermissionChecker.get_user_permissions(request.user, request.organization)
        """
        permissions = {
            'django_perms': [],
            'accounting_perms': [],
            'org_specific_perms': []
        }

        if not user or not user.is_authenticated:
            return permissions

        # Get all user permissions
        user_permissions = user.get_all_permissions()

        for perm in user_permissions:
            if perm.startswith('accounting.'):
                permissions['accounting_perms'].append(perm)
            else:
                permissions['django_perms'].append(perm)

        # Add organization-specific permissions
        if organization:
            org_perms = PermissionChecker._get_org_specific_permissions(user, organization)
            permissions['org_specific_perms'] = org_perms

        return permissions

    @staticmethod
    def filter_queryset_by_permissions(
        user: User,
        queryset: models.QuerySet,
        organization: Optional[Any] = None
    ) -> models.QuerySet:
        """
        Filter queryset based on user permissions.

        Args:
            user: User instance
            queryset: QuerySet to filter
            organization: Organization context

        Returns:
            Filtered QuerySet

        Usage:
            # Filter journals user can see
            visible_journals = PermissionChecker.filter_queryset_by_permissions(
                request.user, Journal.objects.all(), request.organization
            )
        """
        if user.is_superuser:
            return queryset

        model = queryset.model

        # Check if user can view this model
        if not PermissionChecker.has_model_permission(user, model, 'view', organization):
            return queryset.none()

        # Apply organization filtering if needed
        if organization and hasattr(model, 'organization'):
            queryset = OrganizationService.filter_queryset_by_org(queryset, organization)

        # Apply additional permission-based filtering
        # This could include status-based filtering, ownership, etc.

        return queryset

    @staticmethod
    def _has_org_specific_permission(
        user: User,
        app_label: str,
        codename: str,
        organization: Any
    ) -> bool:
        """Check organization-specific permissions."""
        # This would integrate with your org-specific permission system
        # For now, basic organization membership check
        return OrganizationService.validate_org_access(user, organization)

    @staticmethod
    def _get_field_restrictions(user: User, organization: Optional[Any] = None) -> Dict[str, Any]:
        """Get field-level restrictions for user."""
        # This would load from a permission configuration
        # For now, return empty restrictions
        return {
            'restricted_fields': [],
            'special_permissions': {}
        }

    @staticmethod
    def _get_org_specific_permissions(user: User, organization: Any) -> List[str]:
        """Get organization-specific permissions."""
        # This would query org-specific permissions
        # For now, return basic permissions
        return []


class RoleManager:
    """
    Manages user roles and their associated permissions.
    """

    # Predefined roles
    ACCOUNTANT = 'accountant'
    AUDITOR = 'auditor'
    APPROVER = 'approver'
    ADMIN = 'admin'
    VIEWER = 'viewer'

    ROLE_PERMISSIONS = {
        ACCOUNTANT: [
            'accounting.add_journal',
            'accounting.change_journal',
            'accounting.view_journal',
            'accounting.post_journal',
        ],
        AUDITOR: [
            'accounting.view_journal',
            'accounting.export_data',
        ],
        APPROVER: [
            'accounting.approve_journal',
            'accounting.view_journal',
        ],
        ADMIN: [
            'accounting.add_journal',
            'accounting.change_journal',
            'accounting.delete_journal',
            'accounting.view_journal',
            'accounting.approve_journal',
            'accounting.post_journal',
            'accounting.reverse_journal',
            'accounting.manage_fiscal_year',
        ],
        VIEWER: [
            'accounting.view_journal',
        ]
    }

    @staticmethod
    def assign_role(user: User, role: str, organization: Optional[Any] = None) -> bool:
        """
        Assign a role to a user.

        Args:
            user: User instance
            role: Role name
            organization: Organization context (optional)

        Returns:
            True if role was assigned successfully

        Usage:
            # Assign accountant role
            RoleManager.assign_role(user, RoleManager.ACCOUNTANT, organization)
        """
        if role not in RoleManager.ROLE_PERMISSIONS:
            return False

        permissions = RoleManager.ROLE_PERMISSIONS[role]

        # Add permissions to user
        for perm in permissions:
            try:
                app_label, codename = perm.split('.')
                content_type = ContentType.objects.get(app_label=app_label)
                permission = Permission.objects.get(
                    content_type=content_type,
                    codename=codename
                )
                user.user_permissions.add(permission)
            except (ContentType.DoesNotExist, Permission.DoesNotExist):
                continue  # Skip if permission doesn't exist

        # Add to role group if it exists
        try:
            group = Group.objects.get(name=f"{role}_{organization.code if organization else 'global'}")
            user.groups.add(group)
        except Group.DoesNotExist:
            # Create group if it doesn't exist
            group = Group.objects.create(
                name=f"{role}_{organization.code if organization else 'global'}"
            )
            user.groups.add(group)

        return True

    @staticmethod
    def remove_role(user: User, role: str, organization: Optional[Any] = None) -> bool:
        """
        Remove a role from a user.

        Args:
            user: User instance
            role: Role name
            organization: Organization context

        Returns:
            True if role was removed successfully
        """
        if role not in RoleManager.ROLE_PERMISSIONS:
            return False

        permissions = RoleManager.ROLE_PERMISSIONS[role]

        # Remove permissions from user
        for perm in permissions:
            try:
                app_label, codename = perm.split('.')
                content_type = ContentType.objects.get(app_label=app_label)
                permission = Permission.objects.get(
                    content_type=content_type,
                    codename=codename
                )
                user.user_permissions.remove(permission)
            except (ContentType.DoesNotExist, Permission.DoesNotExist):
                continue

        # Remove from role group
        try:
            group = Group.objects.get(name=f"{role}_{organization.code if organization else 'global'}")
            user.groups.remove(group)
        except Group.DoesNotExist:
            pass

        return True

    @staticmethod
    def get_user_roles(user: User, organization: Optional[Any] = None) -> List[str]:
        """
        Get roles assigned to a user.

        Args:
            user: User instance
            organization: Organization context

        Returns:
            List of role names

        Usage:
            # Check user roles
            roles = RoleManager.get_user_roles(request.user, request.organization)
            if RoleManager.APPROVER in roles:
                # Show approval options
        """
        roles = []

        # Check groups for role-based access
        group_names = user.groups.values_list('name', flat=True)

        for role in RoleManager.ROLE_PERMISSIONS.keys():
            group_name = f"{role}_{organization.code if organization else 'global'}"
            if group_name in group_names:
                roles.append(role)

        return roles


class SecurityValidator:
    """
    Security validation utilities.
    """

    @staticmethod
    def validate_data_access(
        user: User,
        data_object: Any,
        action: str,
        organization: Optional[Any] = None
    ) -> Tuple[bool, str]:
        """
        Comprehensive data access validation.

        Args:
            user: User attempting access
            data_object: Object being accessed
            action: Action being performed
            organization: Organization context

        Returns:
            Tuple of (is_valid, error_message)

        Usage:
            # Before allowing data access
            is_valid, error = SecurityValidator.validate_data_access(
                request.user, journal, 'view', request.organization
            )
            if not is_valid:
                raise PermissionDenied(error)
        """
        # Check basic permissions
        if not PermissionChecker.has_model_permission(user, data_object, action, organization):
            return False, f"You don't have permission to {action} this {data_object.__class__.__name__.lower()}"

        # Check organization access
        if hasattr(data_object, 'organization') and organization:
            if data_object.organization != organization:
                return False, "Data belongs to a different organization"

        # Check ownership/access restrictions
        if hasattr(data_object, 'created_by') and data_object.created_by != user:
            # Additional ownership checks could go here
            pass

        # Check status-based restrictions
        if hasattr(data_object, 'status'):
            if data_object.status == 'deleted':
                return False, "This record has been deleted"
            elif data_object.status == 'draft' and action in ['approve', 'post']:
                return False, "Cannot perform this action on draft records"

        return True, ""

    @staticmethod
    def audit_sensitive_action(
        user: User,
        action: str,
        target_object: Any,
        details: Optional[Dict[str, Any]] = None,
        organization: Optional[Any] = None
    ) -> None:
        """
        Audit sensitive actions for compliance.

        Args:
            user: User performing action
            action: Action description
            target_object: Object being acted upon
            details: Additional details
            organization: Organization context

        Usage:
            # Audit sensitive operations
            SecurityValidator.audit_sensitive_action(
                request.user, 'journal_approval', journal,
                {'approved_amount': journal.total_amount}, request.organization
            )
        """
        from .audit_logging import log_action

        log_action(
            user=user,
            organization=organization,
            action=action,
            object_type=target_object.__class__.__name__,
            object_id=target_object.pk,
            details=str(details) if details else None,
            changes=details
        )


# Decorators for permission checking
def require_permission(permission: str, organization_param: str = 'organization'):
    """
    Decorator to require specific permission for view functions.

    Args:
        permission: Permission codename required
        organization_param: Parameter name for organization in view

    Usage:
        @require_permission('accounting.approve_journal')
        def approve_journal(request, journal_id, organization):
            # View logic here
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            organization = kwargs.get(organization_param) or getattr(request, 'organization', None)

            if not PermissionChecker.has_accounting_permission(request.user, permission, organization):
                raise PermissionDenied(f"Permission '{permission}' required")

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_model_permission(action: str, model_param: str = 'obj'):
    """
    Decorator to require model permission for view functions.

    Args:
        action: Permission action ('view', 'change', 'delete')
        model_param: Parameter name for model instance in view

    Usage:
        @require_model_permission('change', 'journal')
        def edit_journal(request, journal, organization):
            # View logic here
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            obj = kwargs.get(model_param)
            organization = kwargs.get('organization') or getattr(request, 'organization', None)

            if not PermissionChecker.has_model_permission(request.user, obj, action, organization):
                raise PermissionDenied(f"Permission to {action} {obj.__class__.__name__} required")

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# Context processor for permissions
def permission_context_processor(request):
    """
    Django context processor to add user permissions to templates.

    Add to settings.TEMPLATES:
    'context_processors': [
        ...
        'utils.permissions.permission_context_processor',
    ]

    Usage:
        # In templates
        {% if perms.accounting.approve_journal %}
            <button>Approve Journal</button>
        {% endif %}
    """
    if not request.user or not request.user.is_authenticated:
        return {'perms': {}}

    organization = getattr(request, 'organization', None)
    permissions = PermissionChecker.get_user_permissions(request.user, organization)

    return {
        'perms': permissions,
        'user_roles': RoleManager.get_user_roles(request.user, organization)
    }
