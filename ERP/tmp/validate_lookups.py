from django.contrib.auth import get_user_model
from django.test import Client
from usermanagement.models import Organization
from accounting.models import AccountType, ChartOfAccount, CostCenter, Vendor

User = get_user_model()
user, _ = User.objects.get_or_create(username='lookup_tester', defaults={'password':'pass'})
# Ensure password settable (set_unusable or set password) - set a usable password for client.force_login
if not user.has_usable_password():
    user.set_password('pass')
    user.save()
org = Organization.objects.create(name='LookupOrg', code='LORG', type='retailer')
# create account type and account
at = AccountType.objects.create(name='asset')
coa = ChartOfAccount.objects.create(organization=org, account_type=at, account_code='2000', account_name='Bank')
cc = CostCenter.objects.create(organization=org, code='CC1', name='Main CC', is_active=True)
# Vendor requires accounts_payable_account (non-null), provide the coa we created
vendor = Vendor.objects.create(organization=org, code='V001', display_name='Vendor One', status='active', accounts_payable_account=coa)

c = Client()
c.force_login(user)
# Ensure user has active organization set (helper available on user)
if hasattr(user, 'set_active_organization'):
    user.set_active_organization(org)

# Attempt endpoints
endpoints = [
    ('accounts', '/accounting/journal-entry/lookup/accounts/'),
    ('cost_centers', '/accounting/journal-entry/lookup/cost-centers/'),
    ('vendors', '/accounting/journal-entry/lookup/vendors/'),
]

for name, url in endpoints:
    resp = c.get(url, {'q': '2', 'limit': 10})
    print(url, '=>', resp.status_code, getattr(resp, 'content', b'')[:200])
    try:
        print('json:', resp.json())
    except Exception as e:
        print('no json', e)

print('done')
