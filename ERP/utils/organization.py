"""
Organization & Multi-tenancy Utilities

Provides centralized organization-aware operations and multi-tenancy support.
Ensures data isolation and organization-specific configurations.
"""

from typing import Optional, Any, Dict, Type, Union
from django.db import models
from django.http import HttpRequest
from django.contrib.auth import get_user_model

from usermanagement.models import Organization

User = get_user_model()


class OrganizationService:
    """
    Centralized service for organization-related operations.

    Provides methods for:
    - Getting current organization from requests
    - Filtering querysets by organization
    - Managing organization-specific settings
    - Ensuring data isolation
    """

    @staticmethod
    def get_current_org(request: HttpRequest) -> Optional[Organization]:
        """
        Get the current organization from the request.

        Args:
            request: Django HttpRequest object

        Returns:
            Organization instance or None

        Usage:
            # In views.py
            org = OrganizationService.get_current_org(request)
            if not org:
                return redirect('organization_selection')
        """
        if not request or not hasattr(request, 'organization'):
            return None
        return request.organization

    @staticmethod
    def filter_queryset_by_org(queryset: models.QuerySet, organization: Organization) -> models.QuerySet:
        """
        Filter a queryset to only include records for the specified organization.

        Args:
            queryset: Django QuerySet to filter
            organization: Organization instance

        Returns:
            Filtered QuerySet

        Usage:
            # In views.py
            accounts = OrganizationService.filter_queryset_by_org(
                Account.objects.all(), request.organization
            )
        """
        if not organization:
            return queryset.none()

        # Check if the model has an organization field
        model = queryset.model
        org_fields = ['organization', 'organization_id']

        for field_name in org_fields:
            if hasattr(model, field_name):
                return queryset.filter(**{field_name: organization})

        # If no organization field found, return unfiltered (for global models)
        return queryset

    @staticmethod
    def get_org_setting(organization: Organization, key: str, default: Any = None) -> Any:
        """
        Get an organization-specific setting.

        Args:
            organization: Organization instance
            key: Setting key to retrieve
            default: Default value if setting not found

        Returns:
            Setting value or default

        Usage:
            # Get organization-specific date format
            date_format = OrganizationService.get_org_setting(
                request.organization, 'date_format', 'YYYY-MM-DD'
            )
        """
        if not organization or not hasattr(organization, 'config'):
            return default

        config = getattr(organization, 'config', None)
        if not config:
            return default

        return getattr(config, key, default)

    @staticmethod
    def ensure_org_isolation(queryset: models.QuerySet, organization: Organization) -> models.QuerySet:
        """
        Ensure queryset is properly isolated to organization.
        Raises exception if organization isolation cannot be enforced.

        Args:
            queryset: QuerySet to secure
            organization: Organization instance

        Returns:
            Organization-filtered QuerySet

        Raises:
            ValueError: If organization isolation cannot be enforced

        Usage:
            # In sensitive operations
            secure_accounts = OrganizationService.ensure_org_isolation(
                Account.objects.all(), request.organization
            )
        """
        if not organization:
            raise ValueError("Organization is required for data isolation")

        filtered_qs = OrganizationService.filter_queryset_by_org(queryset, organization)

        # Verify the queryset was actually filtered
        model = queryset.model
        if hasattr(model, 'organization') or hasattr(model, 'organization_id'):
            # For models that should be organization-scoped, ensure filtering worked
            if str(filtered_qs.query) == str(queryset.query):
                raise ValueError(f"Failed to apply organization isolation to {model.__name__}")

        return filtered_qs

    @staticmethod
    def get_org_users(organization: Organization, active_only: bool = True) -> models.QuerySet:
        """
        Get all users belonging to an organization.

        Args:
            organization: Organization instance
            active_only: Whether to return only active users

        Returns:
            QuerySet of users

        Usage:
            # Get active users for approval workflows
            approvers = OrganizationService.get_org_users(org, active_only=True)
        """
        users = User.objects.filter(organization_users__organization=organization)

        if active_only:
            users = users.filter(is_active=True)

        return users.distinct()

    @staticmethod
    def validate_org_access(user: User, organization: Organization) -> bool:
        """
        Validate that a user has access to a specific organization.

        Args:
            user: User instance
            organization: Organization instance

        Returns:
            True if user has access, False otherwise

        Usage:
            # In permission checks
            if not OrganizationService.validate_org_access(request.user, target_org):
                raise PermissionDenied()
        """
        if not user or not organization:
            return False

        return user.organization_users.filter(organization=organization).exists()

    @staticmethod
    def get_org_context(request: HttpRequest) -> Dict[str, Any]:
        """
        Get organization context for templates and views.

        Args:
            request: HttpRequest object

        Returns:
            Dictionary with organization context

        Usage:
            # In context processors or views
            context = OrganizationService.get_org_context(request)
            # Contains: 'organization', 'org_settings', 'user_orgs', etc.
        """
        org = OrganizationService.get_current_org(request)
        context = {
            'organization': org,
            'has_organization': org is not None,
        }

        if org:
            context.update({
                'org_name': org.name,
                'org_code': org.code,
                'org_settings': getattr(org, 'config', {}),
                'user_orgs': list(request.user.organization_users.values_list(
                    'organization__name', flat=True
                )) if request.user.is_authenticated else [],
            })

        return context


class OrganizationScopedManager(models.Manager):
    """
    Manager that automatically filters querysets by organization.

    Usage:
        class MyModel(models.Model):
            organization = models.ForeignKey(Organization, ...)
            objects = OrganizationScopedManager()

            class Meta:
                # Manager will automatically filter by organization
                pass

        # In views
        org_accounts = MyModel.objects.for_org(request.organization)
    """

    def for_org(self, organization: Organization) -> models.QuerySet:
        """
        Get queryset filtered for specific organization.

        Args:
            organization: Organization instance

        Returns:
            Filtered QuerySet
        """
        return OrganizationService.filter_queryset_by_org(self.get_queryset(), organization)

    def get_queryset(self) -> models.QuerySet:
        """
        Override to add organization-based filtering logic.
        This can be extended by subclasses for specific filtering rules.
        """
        return super().get_queryset()


class OrganizationValidator:
    """
    Validation utilities for organization-related data.
    """

    @staticmethod
    def validate_org_required(instance: models.Model, organization_field: str = 'organization') -> None:
        """
        Validate that an organization is set on a model instance.

        Args:
            instance: Model instance to validate
            organization_field: Name of the organization field

        Raises:
            ValidationError: If organization is not set

        Usage:
            # In model clean() method
            OrganizationValidator.validate_org_required(self)
        """
        from django.core.exceptions import ValidationError

        if not hasattr(instance, organization_field):
            raise ValidationError(f"Model {instance.__class__.__name__} must have an '{organization_field}' field")

        org_value = getattr(instance, organization_field)
        if not org_value:
            raise ValidationError(f"Organization is required for {instance.__class__.__name__}")

    @staticmethod
    def validate_cross_org_access(instance: models.Model, user: User) -> None:
        """
        Validate that a user can access data from a specific organization.

        Args:
            instance: Model instance with organization
            user: User attempting access

        Raises:
            PermissionError: If user cannot access the organization

        Usage:
            # In views before accessing data
            OrganizationValidator.validate_cross_org_access(account, request.user)
        """
        if hasattr(instance, 'organization'):
            org = instance.organization
            if not OrganizationService.validate_org_access(user, org):
                raise PermissionError(f"User {user} cannot access organization {org}")


# Context processor for organization context
def organization_context_processor(request: HttpRequest) -> Dict[str, Any]:
    """
    Django context processor to add organization context to all templates.

    Add to settings.TEMPLATES:
    'context_processors': [
        ...
        'utils.organization.organization_context_processor',
    ]

    Usage:
        # In any template
        {% if organization %}
            Welcome to {{ org_name }}
        {% endif %}
    """
    return OrganizationService.get_org_context(request)
