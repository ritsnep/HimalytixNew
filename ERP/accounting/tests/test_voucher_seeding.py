from django.core.management import call_command
from django.test import TestCase

from accounting.models import Currency, JournalType, VoucherModeConfig
from accounting.services.voucher_seeding import seed_voucher_configs
from accounting.voucher_definitions import VOUCHER_DEFINITIONS, journal_type_seed
from usermanagement.models import Organization


class VoucherSeedingTestCase(TestCase):
    def setUp(self):
        self.currency = Currency.objects.create(
            currency_code="USD",
            currency_name="US Dollar",
            symbol="$",
            is_active=True,
            isdefault=True,
        )
        self.org = Organization.objects.create(
            name="Seed Org",
            code="SEED",
            type="company",
            base_currency_code=self.currency,
        )

    def test_seed_idempotent(self):
        seed_voucher_configs(self.org, reset=False, repair=True)
        seed_voucher_configs(self.org, reset=False, repair=True)
        self.assertEqual(
            VoucherModeConfig.objects.filter(organization=self.org).count(),
            len(VOUCHER_DEFINITIONS),
        )

    def test_seed_repairs_missing_journal_type(self):
        seed_voucher_configs(self.org, reset=False, repair=True)
        code = VOUCHER_DEFINITIONS[0]["code"]
        config = VoucherModeConfig.objects.get(organization=self.org, code=code)
        config.journal_type = None
        config.save(update_fields=["journal_type"])

        seed_voucher_configs(self.org, reset=False, repair=True)
        config.refresh_from_db()
        self.assertIsNotNone(config.journal_type)

    def test_seed_creates_journal_types(self):
        seed_voucher_configs(self.org, reset=False, repair=True)
        self.assertEqual(
            JournalType.objects.filter(organization=self.org).count(),
            len(journal_type_seed()),
        )

    def test_management_command_all(self):
        org2 = Organization.objects.create(
            name="Seed Org 2",
            code="SEED2",
            type="company",
            base_currency_code=self.currency,
        )
        call_command("seed_voucher_definitions", "--org", "all")
        self.assertEqual(
            VoucherModeConfig.objects.filter(organization=self.org).count(),
            len(VOUCHER_DEFINITIONS),
        )
        self.assertEqual(
            VoucherModeConfig.objects.filter(organization=org2).count(),
            len(VOUCHER_DEFINITIONS),
        )
