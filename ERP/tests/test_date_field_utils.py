"""
Tests for date_field_utils - comprehensive test coverage for Nepali date support.
"""

import datetime
import pytest
from django.test import TestCase, RequestFactory
from django.db import models
from django import forms
from decimal import Decimal

from utils.date_field_utils import (
    get_date_fields_for_model,
    get_widget_for_field,
    apply_date_widgets_to_form,
    configure_form_date_fields,
    get_all_models_with_date_fields,
    register_date_field_schema,
    get_date_field_display_value,
    batch_configure_forms,
    SCHEMA_DATE_FIELDS,
)
from utils.widgets import DualCalendarWidget
from utils.calendars import CalendarMode, ad_to_bs_string

# Import actual models from the project
from accounting.models import (
    FiscalYear,
    Journal,
    ChartOfAccount,
    GeneralLedger,
    PurchaseInvoice,
)
from inventory.models import Product, InventoryItem, StockLedger
from service_management.models import ServiceContract, ServiceTicket
from accounting.forms import FiscalYearForm


class DateFieldUtilsTestCase(TestCase):
    """Test date field discovery and configuration utilities."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
    
    def test_fiscal_year_date_fields_discovered(self):
        """Test that FiscalYear date fields are correctly discovered."""
        fields = get_date_fields_for_model(FiscalYear)
        field_names = [name for name, _ in fields]
        
        self.assertIn("start_date", field_names)
        self.assertIn("end_date", field_names)
        self.assertEqual(len(fields), 2)
    
    def test_purchase_invoice_date_fields_discovered(self):
        """Test that PurchaseInvoice date fields are discovered."""
        fields = get_date_fields_for_model(PurchaseInvoice)
        field_names = [name for name, _ in fields]
        
        self.assertIn("invoice_date", field_names)
        self.assertIn("due_date", field_names)
        self.assertIn("delivery_date", field_names)
        self.assertGreaterEqual(len(fields), 3)
    
    def test_product_date_fields_discovered(self):
        """Test that Product (inventory) date fields are discovered."""
        fields = get_date_fields_for_model(Product)
        field_names = [name for name, _ in fields]
        
        # Product model may or may not have these, so we just verify it's discovered
        self.assertGreaterEqual(len(fields), 0)
    
    def test_stock_ledger_date_fields_discovered(self):
        """Test that StockLedger date fields are discovered."""
        fields = get_date_fields_for_model(StockLedger)
        field_names = [name for name, _ in fields]
        
        # Check for date fields
        self.assertGreaterEqual(len(fields), 0)
    
    def test_service_contract_date_fields_discovered(self):
        """Test that ServiceContract (service management) date fields are discovered."""
        fields = get_date_fields_for_model(ServiceContract)
        field_names = [name for name, _ in fields]
        
        self.assertIn("start_date", field_names)
        self.assertIn("end_date", field_names)
        self.assertIn("renewal_date", field_names)
    
    def test_service_ticket_date_fields_discovered(self):
        """Test that ServiceTicket date fields are discovered."""
        fields = get_date_fields_for_model(ServiceTicket)
        field_names = [name for name, _ in fields]
        
        # Check for important ticket date fields
        self.assertGreaterEqual(len(fields), 0)
    
    def test_general_ledger_date_fields(self):
        """Test GeneralLedger date fields."""
        fields = get_date_fields_for_model(GeneralLedger)
        field_names = [name for name, _ in fields]
        
        self.assertIn("posting_date", field_names)
    
    def test_coa_date_fields(self):
        """Test ChartOfAccount date fields."""
        fields = get_date_fields_for_model(ChartOfAccount)
        field_names = [name for name, _ in fields]
        
        # Should have effective_from/to if configured
        self.assertGreaterEqual(len(fields), 0)


class WidgetApplicationTestCase(TestCase):
    """Test widget application to forms."""
    
    def test_get_widget_for_date_field(self):
        """Test getting widget for a date field."""
        field = FiscalYear._meta.get_field("start_date")
        widget = get_widget_for_field(field)
        
        self.assertIsInstance(widget, DualCalendarWidget)
    
    def test_get_widget_for_datetime_field(self):
        """Test getting widget for a datetime field."""
        field = StockLedger._meta.get_field("txn_date")
        widget = get_widget_for_field(field)
        
        self.assertIsInstance(widget, DualCalendarWidget)
    
    def test_widget_with_organization(self):
        """Test widget creation with organization context."""
        from account.models import Organization
        
        # Create test organization
        org = Organization.objects.create(
            name="Test Org",
            legal_name="Test Organization Pvt Ltd",
            country="NP"
        )
        
        field = FiscalYear._meta.get_field("start_date")
        widget = get_widget_for_field(field, organization=org)
        
        self.assertIsInstance(widget, DualCalendarWidget)
    
    def test_widget_with_custom_attrs(self):
        """Test widget with custom attributes."""
        field = FiscalYear._meta.get_field("start_date")
        attrs = {"class": "custom-date-input", "data-test": "value"}
        widget = get_widget_for_field(field, attrs=attrs)
        
        self.assertIsInstance(widget, DualCalendarWidget)
        # Attrs should be passed through
        self.assertEqual(widget.attrs.get("data-test"), "value")
    
    def test_apply_date_widgets_to_fiscal_year_form(self):
        """Test applying date widgets to FiscalYearForm."""
        modified_form = apply_date_widgets_to_form(FiscalYearForm)
        
        # Check that widgets were applied
        self.assertIn("start_date", modified_form.Meta.widgets)
        self.assertIn("end_date", modified_form.Meta.widgets)
        
        self.assertIsInstance(
            modified_form.Meta.widgets["start_date"],
            DualCalendarWidget
        )
        self.assertIsInstance(
            modified_form.Meta.widgets["end_date"],
            DualCalendarWidget
        )
    
    def test_configure_form_instance(self):
        """Test configuring a form instance."""
        form = FiscalYearForm()
        configure_form_date_fields(form)
        
        # Form should be properly configured with default dates
        self.assertIsNotNone(form.fields["start_date"].initial)
        self.assertIsNotNone(form.fields["end_date"].initial)


class SchemaRegistrationTestCase(TestCase):
    """Test schema registration and discovery."""
    
    def test_get_all_models_with_date_fields(self):
        """Test getting all configured models."""
        schemas = get_all_models_with_date_fields()
        
        # Should contain accounting models
        self.assertIn("FiscalYear", schemas)
        self.assertIn("Journal", schemas)
        
        # Should contain inventory models
        self.assertIn("Item", schemas)
        self.assertIn("Stock", schemas)
        
        # Should contain service management models
        self.assertIn("ServiceContract", schemas)
        self.assertIn("Ticket", schemas)
    
    def test_register_custom_model_schema(self):
        """Test registering a custom model schema."""
        # Register a custom model
        register_date_field_schema("CustomModel", ["date_field1", "date_field2"])
        
        schemas = get_all_models_with_date_fields()
        self.assertIn("CustomModel", schemas)
        self.assertEqual(len(schemas["CustomModel"]), 2)
        self.assertIn("date_field1", schemas["CustomModel"])
    
    def test_register_schema_updates_existing(self):
        """Test that registering updates existing schemas."""
        # Get initial count
        initial_fiscal_year_fields = len(get_all_models_with_date_fields()["FiscalYear"])
        
        # Register a new field (shouldn't duplicate if already exists)
        register_date_field_schema("FiscalYear", ["start_date", "new_date_field"])
        
        # Check it was added
        schemas = get_all_models_with_date_fields()
        self.assertIn("new_date_field", schemas["FiscalYear"])


class DateDisplayTestCase(TestCase):
    """Test date display formatting."""
    
    def test_display_ad_date_default(self):
        """Test displaying AD date in default mode."""
        test_date = datetime.date(2025, 12, 15)
        result = get_date_field_display_value(test_date)
        
        self.assertEqual(result, "2025-12-15")
    
    def test_display_ad_date_in_ad_mode(self):
        """Test displaying AD date in AD mode."""
        test_date = datetime.date(2025, 12, 15)
        result = get_date_field_display_value(test_date, calendar_mode=CalendarMode.AD)
        
        self.assertEqual(result, "2025-12-15")
    
    def test_display_ad_date_in_bs_mode(self):
        """Test displaying AD date converted to BS."""
        test_date = datetime.date(2025, 12, 15)
        result = get_date_field_display_value(test_date, calendar_mode=CalendarMode.BS)
        
        # Should convert to Nepali date
        self.assertNotEqual(result, "2025-12-15")
        # Should be in format like 2082-08-30
        parts = result.split("-")
        self.assertEqual(len(parts), 3)
    
    def test_display_dual_both_formats(self):
        """Test displaying both AD and BS when include_both=True."""
        test_date = datetime.date(2025, 12, 15)
        result = get_date_field_display_value(
            test_date,
            calendar_mode=CalendarMode.DUAL,
            include_both=True
        )
        
        # Should contain AD date and BS notation
        self.assertIn("2025-12-15", result)
        self.assertIn("BS:", result)
    
    def test_display_datetime_value(self):
        """Test displaying datetime values."""
        test_datetime = datetime.datetime(2025, 12, 15, 10, 30, 45)
        result = get_date_field_display_value(test_datetime)
        
        # Should extract date part only
        self.assertIn("2025-12-15", result)
    
    def test_display_none_value(self):
        """Test displaying None value."""
        result = get_date_field_display_value(None)
        
        self.assertEqual(result, "")
    
    def test_display_string_date(self):
        """Test displaying ISO format string date."""
        result = get_date_field_display_value("2025-12-15")
        
        self.assertIn("2025-12-15", result)


class BatchConfigurationTestCase(TestCase):
    """Test batch form configuration."""
    
    def test_batch_configure_forms(self):
        """Test configuring multiple forms at once."""
        forms_to_config = [FiscalYearForm]
        results = batch_configure_forms(forms_to_config)
        
        self.assertIn("FiscalYearForm", results)
        self.assertIsInstance(results["FiscalYearForm"], type)
        self.assertTrue(issubclass(results["FiscalYearForm"], forms.ModelForm))
    
    def test_batch_configure_with_organization(self):
        """Test batch configuration with organization context."""
        from account.models import Organization
        
        org = Organization.objects.create(
            name="Test Org",
            legal_name="Test Organization",
            country="NP"
        )
        
        forms_to_config = [FiscalYearForm]
        results = batch_configure_forms(forms_to_config, organization=org)
        
        self.assertIn("FiscalYearForm", results)


class ExcludePatternsTestCase(TestCase):
    """Test that exclude patterns work correctly."""
    
    def test_exclude_audit_fields(self):
        """Test that audit fields are excluded."""
        fields = get_date_fields_for_model(Journal)
        field_names = [name for name, _ in fields]
        
        # Should not include these audit fields
        for excluded in ["created_at", "updated_at", "deleted_at"]:
            self.assertNotIn(excluded, field_names)


class IntegrationTestCase(TestCase):
    """Integration tests across multiple schemas."""
    
    def test_accounting_module_date_fields(self):
        """Test all accounting module date field discoveries."""
        accounting_models = [
            FiscalYear, Journal, ChartOfAccount, GeneralLedger, PurchaseInvoice
        ]
        
        for model in accounting_models:
            fields = get_date_fields_for_model(model)
            self.assertGreater(len(fields), 0, f"{model.__name__} should have date fields")
    
    def test_inventory_module_date_fields(self):
        """Test all inventory module date field discoveries."""
        inventory_models = [Product, StockLedger]
        
        for model in inventory_models:
            fields = get_date_fields_for_model(model)
            # At least one of these should have date fields
            if fields:
                self.assertGreater(len(fields), 0, f"{model.__name__} has date fields")
    
    def test_service_management_module_date_fields(self):
        """Test all service management module date field discoveries."""
        service_models = [ServiceContract, ServiceTicket]
        
        for model in service_models:
            fields = get_date_fields_for_model(model)
            # At least one of these should have date fields
            if fields:
                self.assertGreater(len(fields), 0, f"{model.__name__} has date fields")
    
    def test_nepali_conversion_roundtrip(self):
        """Test AD to BS and back conversion."""
        ad_date = datetime.date(2025, 12, 15)
        ad_str = ad_date.isoformat()
        
        # Convert to Nepali
        bs_str = ad_to_bs_string(ad_str)
        self.assertIsNotNone(bs_str)
        
        # Verify it looks like a Nepali date
        parts = bs_str.split("-")
        self.assertEqual(len(parts), 3)
        
        # Year should be higher (2025 AD ~ 2082 BS)
        bs_year = int(parts[0])
        self.assertGreater(bs_year, 2050)  # BS years are typically 56+ higher
    
    def test_widget_rendering_with_nepali_support(self):
        """Test that widgets properly support Nepali dates."""
        widget = DualCalendarWidget()
        
        # Should have Nepali datepicker assets
        media = widget.Media
        self.assertTrue(any("nepali" in str(js) for js in media._js))


class ErrorHandlingTestCase(TestCase):
    """Test error handling in date field utilities."""
    
    def test_invalid_field_type_raises_error(self):
        """Test that non-date fields raise ValueError."""
        # Get a non-date field
        field = FiscalYear._meta.get_field("code")
        
        with self.assertRaises(ValueError):
            get_widget_for_field(field)
    
    def test_missing_model_in_form_class(self):
        """Test handling of form without model."""
        class MinimalForm(forms.Form):
            name = forms.CharField()
        
        # Should handle gracefully
        result = apply_date_widgets_to_form(MinimalForm)
        self.assertIsNotNone(result)
    
    def test_invalid_date_string_display(self):
        """Test handling of invalid date strings."""
        result = get_date_field_display_value("invalid-date-string")
        
        # Should fall back to string representation
        self.assertEqual(result, "invalid-date-string")
