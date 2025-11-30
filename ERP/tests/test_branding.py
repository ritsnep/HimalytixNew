"""Tests covering tenant-aware branding helpers and context."""
from __future__ import annotations

import uuid

import pytest
from django.templatetags.static import static
from django.test import RequestFactory

from dashboard.context_processors import branding_context
from tenancy.models import Tenant, TenantConfig
from utils.branding import get_branding_for_tenant


@pytest.fixture
def tenant_factory(db):
    """Create tenants with minimal required fields for branding tests."""
    def _create(**overrides) -> Tenant:
        suffix = uuid.uuid4().hex[:6]
        defaults = {
            "code": overrides.get("code", f"TEN-{suffix}"),
            "name": overrides.get("name", f"Tenant {suffix}"),
            "slug": overrides.get("slug", f"tenant-{suffix}"),
            "subscription_tier": overrides.get("subscription_tier", "standard"),
            "is_active": overrides.get("is_active", True),
            "domain_name": overrides.get("domain_name", f"tenant{suffix}.local"),
            "data_schema": overrides.get("data_schema", f"schema_{suffix}"),
        }
        defaults.update(overrides)
        return Tenant.objects.create(**defaults)

    return _create


@pytest.mark.django_db
def test_branding_defaults_without_tenant():
    branding = get_branding_for_tenant()
    assert branding["favicon_url"] == static("images/favicon.ico")
    assert "himalytix-sm.svg" in branding["logo_light_url"]


@pytest.mark.django_db
def test_branding_prefers_tenant_favicon(tenant_factory):
    tenant = tenant_factory()
    custom_favicon = "https://cdn.example.com/assets/acme.ico"
    TenantConfig.objects.create(
        tenant=tenant,
        config_key="branding.favicon_url",
        config_value=custom_favicon,
        data_type="string",
    )

    branding = get_branding_for_tenant(tenant)

    assert branding["favicon_url"] == custom_favicon


@pytest.mark.django_db
def test_branding_ignores_empty_config_values(tenant_factory):
    tenant = tenant_factory()
    TenantConfig.objects.create(
        tenant=tenant,
        config_key="branding.favicon_url",
        config_value="",
        data_type="string",
    )

    branding = get_branding_for_tenant(tenant)

    assert branding["favicon_url"] == static("images/favicon.ico")


@pytest.mark.django_db
def test_branding_context_uses_request_tenant(tenant_factory):
    tenant = tenant_factory()
    custom_favicon = "https://assets.example.com/favicons/tenant.ico"
    TenantConfig.objects.create(
        tenant=tenant,
        config_key="branding.favicon_url",
        config_value=custom_favicon,
        data_type="string",
    )

    request = RequestFactory().get("/")
    request.tenant = tenant

    context = branding_context(request)

    assert context["branding"]["favicon_url"] == custom_favicon
