from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from accounting.models import ChartOfAccount
from usermanagement.models import Organization


class AccountLookupTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser('admin2', 'admin2@example.com', 'pass')
        self.org = Organization.objects.create(code='TST2', name='Test Org 2')
        self.user.organization = self.org
        self.user.save()
        # create a sample account (requires account_type)
        from accounting.models import AccountType
        acct_type = AccountType.objects.create(code='A', name='Asset')
        self.coa = ChartOfAccount.objects.create(organization=self.org, account_type=acct_type, account_code='4000', account_name='Sales')
        self.client = Client()
        self.client.force_login(self.user)

    def test_account_lookup_returns_results(self):
        # Call view directly to avoid tenant middleware resolution in tests
        from django.test import RequestFactory
        from accounting.views.voucher_htmx_handlers import VoucherAccountLookupHtmxView

        rf = RequestFactory()
        request = rf.get('/accounting/vouchers/htmx/account-lookup/', {'q': 'Sale'})
        request.user = self.user
        request.organization = self.org
        view = VoucherAccountLookupHtmxView.as_view()
        resp = view(request)
        self.assertEqual(resp.status_code, 200)
        import json
        data = json.loads(resp.content)
        self.assertIn('results', data)
        self.assertTrue(any(d['code'] == '4000' for d in data['results']))
