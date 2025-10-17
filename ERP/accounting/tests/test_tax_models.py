from django.test import TestCase
from django.db import IntegrityError
from accounting.models import Organization, TaxAuthority, TaxType, TaxCode

class TaxCodeModelTests(TestCase):
    def setUp(self):
        self.org1 = Organization.objects.create(name="Org1", code="ORG1", type="company")
        self.authority1 = TaxAuthority.objects.create(organization=self.org1, name="Authority1")
        self.type1 = TaxType.objects.create(organization=self.org1, name="Type1", authority=self.authority1)

    def test_code_autogenerates_with_prefix(self):
        tax_code = TaxCode.objects.create(
            organization=self.org1,
            name="Tax A",
            tax_type=self.type1,
            tax_authority=self.authority1,
        )
        self.assertTrue(tax_code.code.startswith("TC"))

    def test_code_unique_per_organization(self):
        TaxCode.objects.create(
            organization=self.org1,
            code="DUP",
            name="Tax1",
            tax_type=self.type1,
            tax_authority=self.authority1,
        )
        with self.assertRaises(IntegrityError):
            TaxCode.objects.create(
                organization=self.org1,
                code="DUP",
                name="Tax2",
                tax_type=self.type1,
                tax_authority=self.authority1,
            )
        org2 = Organization.objects.create(name="Org2", code="ORG2", type="company")
        authority2 = TaxAuthority.objects.create(organization=org2, name="Authority2")
        type2 = TaxType.objects.create(organization=org2, name="Type2", authority=authority2)
        # Should not raise since different organization
        TaxCode.objects.create(
            organization=org2,
            code="DUP",
            name="Tax3",
            tax_type=type2,
            tax_authority=authority2,
        )