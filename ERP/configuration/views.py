from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from django.db.models import Q

from api.permissions import IsOrganizationMember

from .models import ConfigurationEntry, FeatureToggle
from .serializers import ConfigurationEntrySerializer, FeatureToggleSerializer


class OrganizationScopedQuerysetMixin:
    def get_request_organization(self):
        return getattr(self.request, "organization", None)


class ConfigurationEntryViewSet(OrganizationScopedQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = ConfigurationEntrySerializer
    permission_classes = [IsAuthenticated, IsOrganizationMember]

    def get_queryset(self):
        organization = self.get_request_organization()
        query = Q(organization__isnull=True)
        if organization:
            query |= Q(organization=organization)
        scope = self.request.query_params.get("scope")
        queryset = ConfigurationEntry.objects.filter(query)
        if scope:
            queryset = queryset.filter(scope=scope)
        return queryset.order_by("organization_id", "scope", "key")


class FeatureToggleViewSet(OrganizationScopedQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = FeatureToggleSerializer
    permission_classes = [IsAuthenticated, IsOrganizationMember]

    def get_queryset(self):
        organization = self.get_request_organization()
        query = Q(organization__isnull=True)
        if organization:
            query |= Q(organization=organization)
        module = self.request.query_params.get("module")
        queryset = FeatureToggle.objects.filter(query)
        if module:
            queryset = queryset.filter(module=module)
        return queryset.order_by("organization_id", "module", "key")
