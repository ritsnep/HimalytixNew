from datetime import date, timedelta

from django.test import TestCase

from configuration.services import ConfigurationService, FeatureToggleService
from configuration.models import ConfigurationEntry, FeatureToggle
from usermanagement.models import CustomUser, Organization
from tenancy.models import Tenant


class ConfigurationServiceTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(code="TEN-001", name="Tenant One", slug="tenant-one", data_schema="ten1")
        self.organization = Organization.objects.create(
            name="Org One",
            code="ORG1",
            type="company",
            tenant=self.tenant,
        )
        self.user = CustomUser.objects.create_user(username="config_user", password="pass", organization=self.organization)

    def test_get_value_prefers_org_specific_then_global(self):
        ConfigurationEntry.objects.create(
            organization=None,
            scope=ConfigurationEntry.SCOPE_FINANCE,
            key="document_numbering",
            value={"journal": "JRN-{YYYY}-{000001}"},
        )
        ConfigurationEntry.objects.create(
            organization=self.organization,
            scope=ConfigurationEntry.SCOPE_FINANCE,
            key="document_numbering",
            value={"journal": "ORG-{YYYY}-{000001}"},
        )

        value = ConfigurationService.get_value(
            organization=self.organization,
            scope=ConfigurationEntry.SCOPE_FINANCE,
            key="document_numbering",
        )
        self.assertEqual(value["journal"], "ORG-{YYYY}-{000001}")

        fallback = ConfigurationService.get_value(
            organization=None,
            scope=ConfigurationEntry.SCOPE_FINANCE,
            key="document_numbering",
        )
        self.assertEqual(fallback["journal"], "JRN-{YYYY}-{000001}")

    def test_set_value_updates_cache_and_entry(self):
        ConfigurationService.set_value(
            organization=self.organization,
            scope=ConfigurationEntry.SCOPE_CORE,
            key="timezone",
            value={"tz": "Asia/Kathmandu"},
            user=self.user,
        )
        entry = ConfigurationEntry.objects.get(organization=self.organization, key="timezone")
        self.assertEqual(entry.value["tz"], "Asia/Kathmandu")


class FeatureToggleServiceTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(code="TEN-002", name="Tenant Two", slug="tenant-two", data_schema="ten2")
        self.organization = Organization.objects.create(
            name="Org Two",
            code="ORG2",
            type="company",
            tenant=self.tenant,
        )

    def test_is_enabled_honors_windows_and_defaults(self):
        FeatureToggle.objects.create(
            organization=self.organization,
            module="finance",
            key="progressive_posting",
            is_enabled=True,
            starts_on=date.today() - timedelta(days=1),
            expires_on=date.today() + timedelta(days=1),
        )
        self.assertTrue(
            FeatureToggleService.is_enabled(
                organization=self.organization,
                module="finance",
                key="progressive_posting",
            )
        )
        self.assertFalse(
            FeatureToggleService.is_enabled(
                organization=None,
                module="finance",
                key="progressive_posting",
                default=False,
            )
        )
