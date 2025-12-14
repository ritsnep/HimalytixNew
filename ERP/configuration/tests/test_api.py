from django.urls import reverse
from rest_framework.test import APITestCase

from configuration.models import ConfigurationEntry, FeatureToggle
from usermanagement.models import CustomUser, Organization
from tenancy.models import Tenant


class ConfigurationApiTests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(code="TEN-API", name="Tenant API", slug="tenant-api", data_schema="tenapi")
        self.organization = Organization.objects.create(
            name="API Org",
            code="APIO",
            type="company",
            tenant=self.tenant,
        )
        self.user = CustomUser.objects.create_user(username="api_user", password="pass", organization=self.organization)
        self.client.force_authenticate(user=self.user)
        ConfigurationEntry.objects.create(
            organization=self.organization,
            scope=ConfigurationEntry.SCOPE_CORE,
            key="locale",
            value={"default": "en"},
        )
        FeatureToggle.objects.create(
            organization=self.organization,
            module="finance",
            key="fast-close",
            is_enabled=True,
        )

    def test_list_configuration_entries_filtered_to_org(self):
        url = reverse("configuration-entry-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["key"], "locale")

    def test_list_feature_toggles(self):
        url = reverse("feature-toggle-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["key"], "fast-close")
