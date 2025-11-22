"""
View tests for accounting views and HTMX endpoints.
"""
from datetime import date

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from accounting.models import VoucherUDFConfig
from accounting.tests import factories

class FiscalYearViewTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='test', password='test')
        self.client.force_login(self.user)

    def test_fiscal_year_list_view(self):
        response = self.client.get(reverse('accounting:fiscal_year_list'))
        self.assertEqual(response.status_code, 200)


class VoucherEntryViewTest(TestCase):
    def setUp(self):
        self.org = factories.create_organization(name="Org", code="ORG")
        self.user = factories.create_user(organization=self.org, username="user1", password="pass", role="superadmin")
        self.client.force_login(self.user)

        self.fy = factories.create_fiscal_year(
            organization=self.org,
            code="FY1",
            name="2024",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            is_current=True,
        )
        self.period = factories.create_accounting_period(
            fiscal_year=self.fy,
            period_number=1,
            name="P1",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            is_current=True,
        )
        self.journal_type = factories.create_journal_type(
            organization=self.org,
            code="GEN",
            name="General",
        )
        factories.create_currency(code="USD", name="US Dollar", symbol="$")
        self.default_config = factories.create_voucher_mode_config(
            organization=self.org,
            journal_type=self.journal_type,
            code="VC1",
            name="Default",
            is_default=True,
            default_currency="USD",
            show_tax_details=False,
            show_dimensions=False,
        )

    def test_voucher_entry_hides_right_sidebar(self):
        response = self.client.get(reverse('accounting:voucher_entry'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Theme Customizer')

    def test_voucher_entry_dynamic_fields_and_udfs(self):
        # Add a second config with different flags and UDFs
        config2 = factories.create_voucher_mode_config(
            organization=self.org,
            journal_type=self.journal_type,
            code="VC2",
            name="With Tax & Dimensions",
            is_default=False,
            show_tax_details=True,
            show_dimensions=True,
            default_currency="USD",
        )
        # Add header and line UDFs to config2
        VoucherUDFConfig.objects.create(
            voucher_mode=config2,
            organization=self.org,
            field_name="custom_header",
            display_name="Custom Header Field",
            field_type="text",
            scope="header",
            is_required=True,
            is_active=True,
        )
        VoucherUDFConfig.objects.create(
            voucher_mode=config2,
            organization=self.org,
            field_name="custom_line",
            display_name="Custom Line Field",
            field_type="number",
            scope="line",
            is_required=False,
            is_active=True,
        )
        # Test default config (no tax/dimensions, no UDFs)
        default_config = self.default_config
        url = reverse('accounting:voucher_entry_config', args=[default_config.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Custom Header Field')
        self.assertNotContains(response, 'Custom Line Field')
        self.assertNotContains(response, 'Tax Code')
        self.assertNotContains(response, 'Department')
        # Test config2 (should show tax, dimensions, and UDFs)
        url2 = reverse('accounting:voucher_entry_config', args=[config2.pk])
        response2 = self.client.get(url2)
        self.assertEqual(response2.status_code, 200)
        self.assertContains(response2, 'Custom Header Field')
        self.assertContains(response2, 'Custom Line Field')
        self.assertContains(response2, 'Tax Code')
        self.assertContains(response2, 'Department')

    def test_voucher_entry_permission_enforcement(self):
        # Create a user with no add/change permissions
        user2 = factories.create_user(organization=self.org, username="user2", password="pass2", role="readonly")
        self.client.force_login(user2)
        config = self.default_config
        url = reverse('accounting:voucher_entry_config', args=[config.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Should not see enabled Add Line or Save Voucher buttons
        self.assertContains(response, 'Add Line')
        self.assertContains(response, 'Save Voucher')
        self.assertInHTML('<button type="button" class="btn btn-add-line mb-3" disabled title="No permission">Add Line</button>', response.content.decode())
        self.assertInHTML('<button type="button" class="btn btn-primary" disabled title="No permission">Save Voucher</button>', response.content.decode())
        # Now test with a user with full permissions
        self.client.force_login(self.user)
        response2 = self.client.get(url)
        self.assertContains(response2, 'Add Line')
        self.assertContains(response2, 'Save Voucher')
        self.assertIn('<button type="button" class="btn btn-add-line mb-3" id="add-journal-line"', response2.content.decode())
        self.assertIn('<button type="submit" class="btn btn-primary">Save Voucher</button>', response2.content.decode())

    def test_voucher_entry_validation_and_error_handling(self):
        config = self.default_config
        # Add a required header UDF
        VoucherUDFConfig.objects.create(
            voucher_mode=config,
            organization=self.org,
            field_name="required_header",
            display_name="Required Header Field",
            field_type="text",
            scope="header",
            is_required=True,
            is_active=True,
        )
        url = reverse('accounting:voucher_entry_config', args=[config.pk])
        # Submit form with missing required header UDF
        post_data = {
            'header-journal_type': self.journal_type.pk,
            'header-period': self.period.pk,
            'header-journal_date': '2024-01-10',
            'header-reference': 'TestRef',
            'header-description': 'TestDesc',
            # 'udf_required_header' is missing
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Required Header Field')
        self.assertContains(response, 'This field is required')
        # Add a required line UDF
        VoucherUDFConfig.objects.create(
            voucher_mode=config,
            organization=self.org,
            field_name="required_line",
            display_name="Required Line Field",
            field_type="number",
            scope="line",
            is_required=True,
            is_active=True,
        )
        # Submit form with missing required line UDF (simulate one line)
        post_data_line = {
            'header-journal_type': self.journal_type.pk,
            'header-period': self.period.pk,
            'header-journal_date': '2024-01-10',
            'header-reference': 'TestRef',
            'header-description': 'TestDesc',
            'lines-TOTAL_FORMS': '1',
            'lines-INITIAL_FORMS': '0',
            'lines-MIN_NUM_FORMS': '0',
            'lines-MAX_NUM_FORMS': '1000',
            'lines-0-account': '',
            'lines-0-description': '',
            'lines-0-debit_amount': '0',
            'lines-0-credit_amount': '0',
            # 'udf_required_line_0' is missing
        }
        response2 = self.client.post(url, post_data_line)
        self.assertEqual(response2.status_code, 200)
        self.assertContains(response2, 'Required Line Field')
        self.assertContains(response2, 'This field is required')