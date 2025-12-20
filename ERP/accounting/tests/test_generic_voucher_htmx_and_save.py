from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounting.models import VoucherModeConfig, Vendor, Customer
from accounting.voucher_schema import ui_schema_to_definition
from accounting.tests.factories import (
    create_accounting_period,
    create_chart_of_account,
    create_journal_type,
    create_organization,
)


class GenericVoucherLookupsAndSaveTests(TestCase):
    def setUp(self):
        self.organization = create_organization()
        self.period = create_accounting_period(organization=self.organization)
        self.journal_type = create_journal_type(organization=self.organization)
        self.coa = create_chart_of_account(organization=self.organization)

        User = get_user_model()
        self.user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='pass12345',
        )
        # Ensure org context is resolvable by UserOrganizationMixin
        if hasattr(self.user, 'organization'):
            self.user.organization = self.organization
            self.user.save(update_fields=['organization'])

        self.client.force_login(self.user)

    def test_generic_voucher_vendor_customer_product_lookups(self):
        ap = create_chart_of_account(organization=self.organization)
        ar = create_chart_of_account(organization=self.organization)

        Vendor.objects.create(
            organization=self.organization,
            code='V001',
            display_name='Vendor One',
            accounts_payable_account=ap,
        )
        Customer.objects.create(
            organization=self.organization,
            code='C001',
            display_name='Customer One',
            accounts_receivable_account=ar,
        )

        try:
            from inventory.models import Product
            Product.objects.create(
                organization=self.organization,
                code='P001',
                name='Product One',
                currency_code='USD',
            )
        except Exception:
            Product = None

        resp = self.client.get(reverse('accounting:generic_voucher_vendor_lookup_hx'), {'q': 'V001', 'limit': 10})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(any(r.get('code') == 'V001' for r in resp.json().get('results', [])))

        resp = self.client.get(reverse('accounting:generic_voucher_customer_lookup_hx'), {'q': 'C001', 'limit': 10})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(any(r.get('code') == 'C001' for r in resp.json().get('results', [])))

        if Product is not None:
            resp = self.client.get(reverse('accounting:generic_voucher_product_lookup_hx'), {'q': 'P001', 'limit': 10})
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(any(r.get('code') == 'P001' for r in resp.json().get('results', [])))

    def test_journal_entry_lookup_endpoints_shape_and_results(self):
        # COA lookup (exact endpoint requested for generic voucher typeahead)
        resp = self.client.get(reverse('accounting:journal_account_lookup'), {'q': self.coa.account_code})
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertTrue(payload.get('ok'))
        self.assertTrue(any(r.get('id') == self.coa.pk for r in payload.get('results', [])))

        # Vendor/customer lookups in same reusable shape
        ap = create_chart_of_account(organization=self.organization)
        ar = create_chart_of_account(organization=self.organization)
        v = Vendor.objects.create(
            organization=self.organization,
            code='V100',
            display_name='Vendor Hundred',
            accounts_payable_account=ap,
        )
        c = Customer.objects.create(
            organization=self.organization,
            code='C100',
            display_name='Customer Hundred',
            accounts_receivable_account=ar,
        )

        resp = self.client.get(reverse('accounting:journal_vendor_lookup'), {'q': 'V100'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json().get('ok'))
        self.assertTrue(any(r.get('id') == getattr(v, 'vendor_id', None) or r.get('code') == 'V100' for r in resp.json().get('results', [])))

        resp = self.client.get(reverse('accounting:journal_customer_lookup'), {'q': 'C100'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json().get('ok'))
        self.assertTrue(any(r.get('id') == getattr(c, 'customer_id', None) or r.get('code') == 'C100' for r in resp.json().get('results', [])))

    def test_generic_voucher_uses_journal_account_lookup_endpoint(self):
        from accounting.models import JournalLine
        from accounting.forms_factory import VoucherFormFactory

        # Build a line-level schema form (VoucherFormFactory expects a direct field schema dict here)
        schema = {'account': {'type': 'select', 'label': 'Account', 'required': True, 'choices': 'ChartOfAccount'}}
        factory = VoucherFormFactory(configuration=schema, model=JournalLine, organization=self.organization, prefix='lines')
        FormCls = factory.build_form()
        form = FormCls()
        self.assertIn('account_display', form.fields)
        self.assertEqual(
            form.fields['account_display'].widget.attrs.get('data-endpoint'),
            '/accounting/journal-entry/lookup/accounts/',
        )

    def test_generic_voucher_create_sets_parent_fk_and_line_number(self):
        ui_schema = {
            'header': {
                'journal_type': {'type': 'select', 'label': 'Journal Type', 'required': True, 'choices': 'JournalType'},
                'period': {'type': 'select', 'label': 'Period', 'required': True, 'choices': 'AccountingPeriod'},
                'journal_date': {'type': 'date', 'label': 'Date', 'required': True},
                'reference': {'type': 'char', 'label': 'Reference', 'required': False},
                'description': {'type': 'char', 'label': 'Description', 'required': False},
                'currency_code': {'type': 'char', 'label': 'Currency', 'required': True},
            },
            'lines': {
                'account': {'type': 'select', 'label': 'Account', 'required': True, 'choices': 'ChartOfAccount'},
                'debit_amount': {'type': 'decimal', 'label': 'Debit', 'required': False},
                'credit_amount': {'type': 'decimal', 'label': 'Credit', 'required': False},
                'description': {'type': 'char', 'label': 'Line Desc', 'required': False},
            },
        }

        config = VoucherModeConfig.objects.create(
            code='je-test',
            name='JE Test',
            organization=self.organization,
            module='accounting',
            journal_type=self.journal_type,
            schema_definition=ui_schema_to_definition(ui_schema),
            is_active=True,
        )

        url = reverse('accounting:generic_voucher_create', kwargs={'voucher_code': config.code})
        post_data = {
            'header-journal_type': str(self.journal_type.pk),
            'header-period': str(self.period.pk),
            'header-journal_date': timezone.now().date().isoformat(),
            'header-currency_code': 'USD',
            'lines-TOTAL_FORMS': '1',
            'lines-INITIAL_FORMS': '0',
            'lines-MIN_NUM_FORMS': '0',
            'lines-MAX_NUM_FORMS': '1000',
            'lines-0-account': str(getattr(self.coa, 'account_id', None) or self.coa.pk),
            'lines-0-account_display': f"{self.coa.account_code} - {self.coa.account_name}",
            'lines-0-debit_amount': '10',
            'lines-0-credit_amount': '0',
        }

        resp = self.client.post(url, data=post_data)
        self.assertEqual(resp.status_code, 302)

        from accounting.models import Journal, JournalLine
        journal = Journal.objects.filter(organization=self.organization).order_by('-journal_id').first()
        self.assertIsNotNone(journal)
        line = JournalLine.objects.filter(journal=journal).first()
        self.assertIsNotNone(line)
        self.assertEqual(line.line_number, 1)

    def test_generic_voucher_validate_returns_422(self):
        ui_schema = {
            'header': {
                'journal_date': {'type': 'date', 'label': 'Date', 'required': True},
                'currency_code': {'type': 'char', 'label': 'Currency', 'required': True},
            },
            'lines': {
                'account': {'type': 'select', 'label': 'Account', 'required': True, 'choices': 'ChartOfAccount'},
                'debit_amount': {'type': 'decimal', 'label': 'Debit', 'required': False},
            },
        }

        config = VoucherModeConfig.objects.create(
            code='val-test',
            name='Validation Test',
            organization=self.organization,
            module='accounting',
            journal_type=self.journal_type,
            schema_definition=ui_schema_to_definition(ui_schema),
            is_active=True,
        )

        url = reverse('accounting:generic_voucher_validate', kwargs={'voucher_code': config.code})
        resp = self.client.post(url, data={'header-currency_code': 'USD'}, HTTP_HX_REQUEST='true')
        self.assertEqual(resp.status_code, 422)
