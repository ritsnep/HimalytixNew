from django import forms

from accounting.forms_factory import VoucherFormFactory
from accounting.models import PurchaseInvoiceLine, PurchaseOrderVoucher


def _assert_typeahead(factory, field_name, expected_endpoint, expected_class_contains=None):
    pair = factory._maybe_build_fk_typeahead_fields(field_name, {'label': field_name})
    assert pair is not None, f"No typeahead pair for {field_name}"
    base_field, display_field = pair
    # base field should be a ModelChoiceField with HiddenInput
    assert isinstance(base_field, forms.ModelChoiceField)
    assert base_field.widget.__class__.__name__ == 'HiddenInput'

    # display field should be CharField with data-endpoint attribute
    assert isinstance(display_field, forms.CharField)
    attrs = display_field.widget.attrs
    assert attrs.get('data-endpoint') == expected_endpoint
    if expected_class_contains:
        assert expected_class_contains in attrs.get('class', '')


def test_chartofaccount_typeahead_on_purchase_invoice_line():
    factory = VoucherFormFactory({}, model=PurchaseInvoiceLine)
    _assert_typeahead(factory, 'account', '/accounting/journal-entry/lookup/accounts/', expected_class_contains='account-typeahead')


def test_taxcode_and_costcenter_typeaheads_on_purchase_invoice_line():
    factory = VoucherFormFactory({}, model=PurchaseInvoiceLine)
    _assert_typeahead(factory, 'tax_code', '/accounting/journal-entry/lookup/tax-codes/')
    _assert_typeahead(factory, 'cost_center', '/accounting/journal-entry/lookup/cost-centers/')
    _assert_typeahead(factory, 'department', '/accounting/journal-entry/lookup/departments/')


def test_vendor_typeahead_on_purchase_order_voucher():
    factory = VoucherFormFactory({}, model=PurchaseOrderVoucher)
    _assert_typeahead(factory, 'vendor', '/accounting/journal-entry/lookup/vendors/')


from django.test import TestCase, Client
from django.contrib.auth import get_user_model


class VoucherLookupHTMXTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='tester', password='pass')
        from usermanagement.models import Organization
        from accounting.models import AccountType, ChartOfAccount

        self.org = Organization.objects.create(name='Org', code='ORG', type='retailer')
        # minimal account type
        self.at = AccountType.objects.create(name='asset')
        # create an account
        self.coa = ChartOfAccount.objects.create(
            organization=self.org,
            account_type=self.at,
            account_code='1000',
            account_name='Cash'
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_voucher_account_lookup_hx_returns_json(self):
        url = '/accounting/vouchers/htmx/account-lookup/'
        resp = self.client.get(url, {'q': '1000', 'limit': 10})
        # Should return JSON with results (200)
        assert resp.status_code == 200, f"Unexpected status: {resp.status_code} {resp.content[:200]}"
        data = resp.json()
        assert 'results' in data
        assert any('Cash' in r.get('text', '') for r in data['results'])
