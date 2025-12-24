from django.contrib.auth import get_user_model
from django.test import Client
from decimal import Decimal
from django.utils import timezone

from accounting.models import Organization, Currency, ChartOfAccount, AccountType, Vendor

User = get_user_model()

organization = Organization.objects.create(name="Debug Org", code="DBG")
expense_account_type = AccountType.objects.create(name="Expense", nature="expense", display_order=5)
asset_account_type = AccountType.objects.create(name="Asset", nature="asset", display_order=1)
account = ChartOfAccount.objects.create(
    organization=organization,
    account_code="5001",
    account_name="Purchases",
    account_type=expense_account_type,
)
vendor = Vendor.objects.create(
    organization=organization,
    code="V001",
    display_name="Test Vendor",
    accounts_payable_account=account,
)
bank_account = ChartOfAccount.objects.create(
    organization=organization,
    account_code="1020",
    account_name="Bank of Test",
    account_type=asset_account_type,
    is_bank_account=True,
)
currency = Currency.objects.create(currency_code='USD', currency_name='US Dollar')

client = Client()
user = User.objects.create_user(username='debug_user', password='pw')
user.organization = organization
user.save()
client.login(username='debug_user', password='pw')
data = {
    'organization': organization.id,
    'vendor': vendor.vendor_id,
    'invoice_number': 'PI200',
    'invoice_date': timezone.now().date(),
    'currency': currency.currency_code,
    'exchange_rate': '1',
    'items-TOTAL_FORMS': '2',
    'items-INITIAL_FORMS': '0',
    'items-0-description': 'Item A',
    'items-0-product': '',
    'items-0-quantity': '2',
    'items-0-unit_cost': '100',
    'items-0-account': account.account_id,
    'items-1-description': 'Item B',
    'items-1-product': '',
    'items-1-quantity': '1',
    'items-1-unit_cost': '200',
    'items-1-account': account.account_id,
    'payments-TOTAL_FORMS': '1',
    'payments-INITIAL_FORMS': '0',
    'payments-0-payment_method': 'bank',
    'payments-0-cash_bank_id': str(bank_account.account_id),
    'payments-0-due_date': timezone.now().date(),
    'payments-0-amount': '200',
}
response = client.post('/accounting/purchase-invoice/new-enhanced/', data, HTTP_HX_REQUEST='true')
print('status', response.status_code)
print(response.content.decode())
try:
    print('json', response.json())
except Exception:
    pass
