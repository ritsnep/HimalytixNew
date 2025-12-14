from datetime import date

from django.test import TestCase

from accounting.models import Currency, DocumentSequenceConfig, FiscalYear
from tenancy.models import Tenant
from usermanagement.models import Organization


class DocumentSequenceIsolationTests(TestCase):
    """Ensure numbering sequences stay tenant/org scoped as mandated by SYSTEM.md."""

    def setUp(self):
        self.currency = Currency.objects.create(
            currency_code='USD',
            currency_name='US Dollar',
            symbol='$',
            isdefault=True,
        )
        self.tenant = Tenant.objects.create(
            code='TENANT-001',
            name='Tenant One',
            slug='tenant-one',
            data_schema='tenant_one',
        )
        self.org_a = Organization.objects.create(
            name='Org Alpha',
            code='ORGA',
            type='company',
            base_currency_code=self.currency,
            tenant=self.tenant,
        )
        self.org_b = Organization.objects.create(
            name='Org Beta',
            code='ORGB',
            type='company',
            base_currency_code=self.currency,
            tenant=self.tenant,
        )

        self._ensure_fiscal_year(self.org_a, code='FY25A')
        self._ensure_fiscal_year(self.org_b, code='FY25B')

    def _ensure_fiscal_year(self, organization, *, code):
        FiscalYear.objects.create(
            organization=organization,
            code=code,
            name=code,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            status='open',
            is_current=True,
            is_default=True,
        )

    def test_sequences_reset_per_organization(self):
        """A document type must maintain unique sequences per organization."""
        first_a = DocumentSequenceConfig.get_next_number(
            organization=self.org_a,
            document_type='sales_invoice',
        )
        second_a = DocumentSequenceConfig.get_next_number(
            organization=self.org_a,
            document_type='sales_invoice',
        )
        first_b = DocumentSequenceConfig.get_next_number(
            organization=self.org_b,
            document_type='sales_invoice',
        )

        self.assertNotEqual(first_a, second_a)
        self.assertTrue(
            second_a.endswith('0002'),
            f"Expected Org A sequence to increment independently, got {second_a}",
        )
        self.assertTrue(
            first_b.endswith('0001'),
            f"Org B should start at sequence 1 despite Org A activity, got {first_b}",
        )

        self.assertEqual(
            DocumentSequenceConfig.objects.filter(organization=self.org_a).count(),
            1,
        )
        self.assertEqual(
            DocumentSequenceConfig.objects.filter(organization=self.org_b).count(),
            1,
        )
