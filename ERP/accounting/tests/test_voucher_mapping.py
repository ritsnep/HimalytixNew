from django.test import TestCase

from accounting.models import VoucherModeConfig
from accounting.services.voucher_seeding import seed_voucher_configs
from accounting.voucher_definitions import VOUCHER_DEFINITIONS
from accounting.tests.factories import create_organization, create_currency


class VoucherMappingTests(TestCase):
    def setUp(self):
        self.currency = create_currency(code="USD")
        self.org = create_organization(base_currency=self.currency)
        seed_voucher_configs(self.org, reset=False, repair=True)

    def test_voucher_code_maps_to_expected_journal_type(self):
        expected = {item["code"]: item["journal_type_code"] for item in VOUCHER_DEFINITIONS}
        for code, journal_code in expected.items():
            config = VoucherModeConfig.objects.get(organization=self.org, code=code)
            self.assertIsNotNone(config.journal_type, f"{code} missing journal_type")
            self.assertEqual(config.journal_type.code, journal_code)

    def test_core_voucher_mappings(self):
        samples = {
            "SALES-INVOICE": "SI",
            "PURCHASE-INVOICE": "PI",
            "AR-RECEIPT": "ARR",
            "AP-PAYMENT": "APP",
            "BANK-RECEIPT": "BR",
            "BANK-PAYMENT": "BP",
            "CASH-RECEIPT": "CR",
            "CASH-PAYMENT": "CP",
        }
        for code, journal_code in samples.items():
            config = VoucherModeConfig.objects.get(organization=self.org, code=code)
            self.assertEqual(config.journal_type.code, journal_code)
