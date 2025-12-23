from django.test import TestCase
from voucher_config.models import VoucherConfigMaster
from usermanagement.models import Organization


class VoucherConfigMasterTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Test Org')

    def test_resolve_ui_schema_valid(self):
        config = VoucherConfigMaster.objects.create(
            organization=self.org,
            code='test',
            label='Test',
            schema_definition={
                'header_fields': [{'name': 'date', 'type': 'date'}],
                'line_fields': [{'name': 'amount', 'type': 'decimal'}]
            }
        )
        schema = config.resolve_ui_schema()
        self.assertIn('header_fields', schema)
        self.assertIn('line_fields', schema)

    def test_resolve_ui_schema_invalid_field_type(self):
        config = VoucherConfigMaster.objects.create(
            organization=self.org,
            code='test2',
            label='Test2',
            schema_definition={
                'header_fields': [{'name': 'date', 'type': 'invalid_type'}]
            }
        )
        schema = config.resolve_ui_schema()
        self.assertIn('error', schema)
        self.assertIn('CFG-001', schema['error'])


class DraftServiceTests(TestCase):
    def test_save_draft_success(self):
        # Test draft save
        pass

    def test_rollback_on_inventory_failure(self):
        # Test rollback
        pass

    def test_idempotency(self):
        # Test double post
        pass