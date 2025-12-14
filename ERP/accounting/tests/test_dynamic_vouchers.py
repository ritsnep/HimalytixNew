"""
Test suite for Dynamic Voucher System

This module contains comprehensive tests for the configuration-driven voucher form generation system.
It tests form creation, formset creation, model mappings, and integration with various voucher configurations.

Run with: python manage.py test accounting.tests.test_dynamic_vouchers
"""

import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.apps import apps

from accounting.models import (
    VoucherConfiguration, Journal, JournalLine,
    PurchaseOrderVoucher, PurchaseReturnVoucher,
    SalesOrderVoucher, PurchaseOrderVoucherLine,
    PurchaseReturnVoucherLine, SalesOrderVoucherLine
)
from accounting.forms.form_factory import VoucherFormFactory
from usermanagement.models import Organization


class DynamicVoucherTestCase(TestCase):
    """Test cases for dynamic voucher form generation."""

    def setUp(self):
        """Set up test data."""
        self.organization = Organization.objects.create(
            name="Test Organization",
            base_currency_code_id="USD"
        )
        self.user = get_user_model().objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

    def test_voucher_configuration_exists(self):
        """Test that voucher configurations exist in the database."""
        configs = VoucherConfiguration.objects.all()
        self.assertGreater(configs.count(), 0, "Should have voucher configurations")

        # Check for required modules
        modules = configs.values_list('module', flat=True).distinct()
        required_modules = ['accounting', 'purchasing', 'sales']
        for module in required_modules:
            self.assertIn(module, modules, f"Should have {module} configurations")

    def test_model_mappings_accounting(self):
        """Test model mappings for accounting module configurations."""
        accounting_configs = VoucherConfiguration.objects.filter(module='accounting')

        for config in accounting_configs[:3]:  # Test first 3
            with self.subTest(config=config.name):
                header_model = VoucherFormFactory._get_model_for_voucher_config(config)
                line_model = VoucherFormFactory._get_line_model_for_voucher_config(config)

                self.assertEqual(header_model, Journal, f"Accounting config should map to Journal model")
                self.assertEqual(line_model, JournalLine, f"Accounting config should map to JournalLine model")

    def test_model_mappings_purchasing(self):
        """Test model mappings for purchasing module configurations."""
        purchase_order_config = VoucherConfiguration.objects.filter(
            module='purchasing', code='purchase_order'
        ).first()
        purchase_return_config = VoucherConfiguration.objects.filter(
            module='purchasing', code='purchase_return'
        ).first()

        if purchase_order_config:
            header_model = VoucherFormFactory._get_model_for_voucher_config(purchase_order_config)
            line_model = VoucherFormFactory._get_line_model_for_voucher_config(purchase_order_config)

            self.assertEqual(header_model, PurchaseOrderVoucher)
            self.assertEqual(line_model, PurchaseOrderVoucherLine)

        if purchase_return_config:
            header_model = VoucherFormFactory._get_model_for_voucher_config(purchase_return_config)
            line_model = VoucherFormFactory._get_line_model_for_voucher_config(purchase_return_config)

            self.assertEqual(header_model, PurchaseReturnVoucher)
            self.assertEqual(line_model, PurchaseReturnVoucherLine)

    def test_model_mappings_sales(self):
        """Test model mappings for sales module configurations."""
        sales_order_config = VoucherConfiguration.objects.filter(
            module='sales', code='sales_order'
        ).first()

        if sales_order_config:
            header_model = VoucherFormFactory._get_model_for_voucher_config(sales_order_config)
            line_model = VoucherFormFactory._get_line_model_for_voucher_config(sales_order_config)

            self.assertEqual(header_model, SalesOrderVoucher)
            self.assertEqual(line_model, SalesOrderVoucherLine)

    def test_form_creation_accounting(self):
        """Test form creation for accounting configurations."""
        config = VoucherConfiguration.objects.filter(module='accounting').first()

        if config:
            form = VoucherFormFactory.get_generic_voucher_form(config, self.organization)
            formset = VoucherFormFactory.get_generic_voucher_formset(config, self.organization)

            self.assertIsNotNone(form)
            self.assertIsNotNone(formset)

            # Test form instance creation
            form_instance = form()
            self.assertIsInstance(form_instance, form)

            # Test formset instance creation
            formset_instance = formset()
            self.assertGreaterEqual(len(formset_instance.forms), 1)

    def test_form_creation_purchasing(self):
        """Test form creation for purchasing configurations."""
        configs = VoucherConfiguration.objects.filter(module='purchasing')

        for config in configs[:2]:  # Test first 2
            with self.subTest(config=config.name):
                form = VoucherFormFactory.get_generic_voucher_form(config, self.organization)
                formset = VoucherFormFactory.get_generic_voucher_formset(config, self.organization)

                self.assertIsNotNone(form)
                self.assertIsNotNone(formset)

    def test_form_creation_sales(self):
        """Test form creation for sales configurations."""
        configs = VoucherConfiguration.objects.filter(module='sales')

        for config in configs[:2]:  # Test first 2
            with self.subTest(config=config.name):
                form = VoucherFormFactory.get_generic_voucher_form(config, self.organization)
                formset = VoucherFormFactory.get_generic_voucher_formset(config, self.organization)

                self.assertIsNotNone(form)
                self.assertIsNotNone(formset)

    def test_form_schema_validation(self):
        """Test that forms are created with correct fields from schema."""
        config = VoucherConfiguration.objects.filter(module='purchasing', code='purchase_return').first()

        if config and config.ui_schema:
            form = VoucherFormFactory.get_generic_voucher_form(config, self.organization)
            form_instance = form()

            # Check that expected fields exist
            expected_fields = ['supplier', 'narration', 'voucher_date', 'original_invoice']
            for field_name in expected_fields:
                self.assertIn(field_name, form_instance.fields,
                            f"Form should have field: {field_name}")

    def test_formset_schema_validation(self):
        """Test that formsets are created with correct fields from schema."""
        config = VoucherConfiguration.objects.filter(module='purchasing', code='purchase_return').first()

        if config and config.ui_schema:
            formset = VoucherFormFactory.get_generic_voucher_formset(config, self.organization)
            formset_instance = formset()

            if formset_instance.forms:
                first_form = formset_instance.forms[0]
                # Check that expected line fields exist
                expected_fields = ['item', 'reason', 'quantity', 'unit_price']
                for field_name in expected_fields:
                    self.assertIn(field_name, first_form.fields,
                                f"Formset form should have field: {field_name}")

    def test_duplicate_configurations_handling(self):
        """Test that duplicate (module, code) pairs are handled correctly."""
        # Find configurations with duplicate (module, code)
        from django.db.models import Count
        duplicates = VoucherConfiguration.objects.values('module', 'code') \
            .annotate(count=Count('id')).filter(count__gt=1)

        for dup in duplicates:
            configs = VoucherConfiguration.objects.filter(
                module=dup['module'], code=dup['code']
            )

            # All configs with same (module, code) should map to same models
            first_config = configs.first()
            first_header_model = VoucherFormFactory._get_model_for_voucher_config(first_config)
            first_line_model = VoucherFormFactory._get_line_model_for_voucher_config(first_config)

            for config in configs:
                header_model = VoucherFormFactory._get_model_for_voucher_config(config)
                line_model = VoucherFormFactory._get_line_model_for_voucher_config(config)

                self.assertEqual(header_model, first_header_model,
                               f"Duplicate configs should map to same header model")
                self.assertEqual(line_model, first_line_model,
                               f"Duplicate configs should map to same line model")

    def test_inventory_module_fallback(self):
        """Test that inventory module falls back to Journal models."""
        # Create a mock inventory config for testing
        inventory_config = VoucherConfiguration(
            module='inventory',
            code='test_inventory',
            name='Test Inventory Config',
            organization=self.organization,
            ui_schema={'header': [], 'lines': []}
        )

        header_model = VoucherFormFactory._get_model_for_voucher_config(inventory_config)
        line_model = VoucherFormFactory._get_line_model_for_voucher_config(inventory_config)

        self.assertEqual(header_model, Journal)
        self.assertEqual(line_model, JournalLine)

    def test_unknown_module_fallback(self):
        """Test that unknown modules fall back to Journal models."""
        unknown_config = VoucherConfiguration(
            module='unknown_module',
            code='test_unknown',
            name='Test Unknown Config',
            organization=self.organization,
            ui_schema={'header': [], 'lines': []}
        )

        header_model = VoucherFormFactory._get_model_for_voucher_config(unknown_config)
        line_model = VoucherFormFactory._get_line_model_for_voucher_config(unknown_config)

        self.assertEqual(header_model, Journal)
        self.assertEqual(line_model, JournalLine)

    def test_form_factory_methods_exist(self):
        """Test that all required methods exist on VoucherFormFactory."""
        required_methods = [
            'get_generic_voucher_form',
            'get_generic_voucher_formset',
            '_get_model_for_voucher_config',
            '_get_line_model_for_voucher_config'
        ]

        for method_name in required_methods:
            self.assertTrue(hasattr(VoucherFormFactory, method_name),
                          f"VoucherFormFactory should have method: {method_name}")
            method = getattr(VoucherFormFactory, method_name)
            self.assertTrue(callable(method),
                          f"{method_name} should be callable")


class DynamicVoucherIntegrationTestCase(TestCase):
    """Integration tests for the complete voucher creation workflow."""

    def setUp(self):
        self.organization = Organization.objects.create(
            name="Integration Test Org",
            base_currency_code_id="USD"
        )

    def test_complete_voucher_workflow(self):
        """Test complete voucher creation workflow."""
        config = VoucherConfiguration.objects.filter(module='purchasing', code='purchase_return').first()

        if config:
            # Create form and formset
            form = VoucherFormFactory.get_generic_voucher_form(config, self.organization)
            formset = VoucherFormFactory.get_generic_voucher_formset(config, self.organization)

            # Create instances
            form_instance = form()
            formset_instance = formset()

            # Verify they can be rendered (basic validation)
            self.assertIsNotNone(form_instance.as_p())
            self.assertIsNotNone(formset_instance.as_p())

            # Verify form is bound to correct model
            self.assertEqual(form_instance._meta.model, PurchaseReturnVoucher)
            self.assertEqual(formset_instance.form._meta.model, PurchaseReturnVoucherLine)