import os
import django
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard.settings')
django.setup()

from usermanagement.models import Organization, CustomUser
from accounting.models import FiscalYear, AccountingPeriod, AccountType, ChartOfAccount, Currency

class Command(BaseCommand):
    help = 'Sets up the initial data required for testing the journal entry module.'

    def handle(self, *args, **options):
        self.stdout.write("Starting test environment setup...")

        # 1. Create a test organization
        organization, org_created = Organization.objects.get_or_create(
            name="TestCorp",
            defaults={'is_active': True}
        )
        if org_created:
            self.stdout.write(self.style.SUCCESS(f"Organization '{organization.name}' created."))
        else:
            self.stdout.write(self.style.NOTICE(f"Organization '{organization.name}' already exists."))

        # 2. Create a test user
        user, user_created = CustomUser.objects.get_or_create(
            username="testuser",
            defaults={
                'email': 'testuser@testcorp.com',
                'organization': organization,
            }
        )
        if user_created:
            user.set_password('testpassword')
            user.save()
            self.stdout.write(self.style.SUCCESS(f"User '{user.username}' created."))
        else:
            self.stdout.write(self.style.NOTICE(f"User '{user.username}' already exists."))

        # 3. Create a default currency if it doesn't exist
        currency, curr_created = Currency.objects.get_or_create(
            currency_code="USD",
            defaults={'currency_name': 'US Dollar', 'symbol': '$'}
        )
        if curr_created:
            self.stdout.write(self.style.SUCCESS(f"Currency '{currency.currency_code}' created."))
        else:
            self.stdout.write(self.style.NOTICE(f"Currency '{currency.currency_code}' already exists."))

        # 4. Create a fiscal year
        today = timezone.now().date()
        fiscal_year, fy_created = FiscalYear.objects.get_or_create(
            organization=organization,
            code="FY2024",
            defaults={
                'name': "Fiscal Year 2024",
                'start_date': today.replace(month=1, day=1),
                'end_date': today.replace(month=12, day=31),
                'is_current': True
            }
        )
        if fy_created:
            self.stdout.write(self.style.SUCCESS(f"Fiscal Year '{fiscal_year.name}' created."))
        else:
            self.stdout.write(self.style.NOTICE(f"Fiscal Year '{fiscal_year.name}' already exists."))

        # 5. Create an open accounting period
        accounting_period, ap_created = AccountingPeriod.objects.get_or_create(
            fiscal_year=fiscal_year,
            name="Current Period",
            defaults={
                'period_number': today.month,
                'start_date': today.replace(day=1),
                'end_date': (today.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1),
                'status': 'open'
            }
        )
        if ap_created:
            self.stdout.write(self.style.SUCCESS(f"Accounting Period '{accounting_period.name}' created."))
        else:
            self.stdout.write(self.style.NOTICE(f"Accounting Period '{accounting_period.name}' already exists."))

        # 6. Create Account Types
        account_types_data = [
            {'name': 'Asset', 'nature': 'asset', 'display_order': 1},
            {'name': 'Liability', 'nature': 'liability', 'display_order': 2},
            {'name': 'Equity', 'nature': 'equity', 'display_order': 3},
            {'name': 'Income', 'nature': 'income', 'display_order': 4},
            {'name': 'Expense', 'nature': 'expense', 'display_order': 5},
        ]
        account_types = {}
        for at_data in account_types_data:
            at, at_created = AccountType.objects.get_or_create(
                name=at_data['name'],
                defaults=at_data
            )
            account_types[at_data['nature']] = at
            if at_created:
                self.stdout.write(self.style.SUCCESS(f"Account Type '{at.name}' created."))
            else:
                self.stdout.write(self.style.NOTICE(f"Account Type '{at.name}' already exists."))

        # 7. Create a sample Chart of Accounts
        chart_of_accounts_data = [
            {'account_code': '1010', 'account_name': 'Cash', 'account_type': 'asset'},
            {'account_code': '1200', 'account_name': 'Accounts Receivable', 'account_type': 'asset'},
            {'account_code': '2010', 'account_name': 'Accounts Payable', 'account_type': 'liability'},
            {'account_code': '3010', 'account_name': 'Common Stock', 'account_type': 'equity'},
            {'account_code': '4010', 'account_name': 'Sales Revenue', 'account_type': 'income'},
            {'account_code': '5010', 'account_name': 'Office Supplies Expense', 'account_type': 'expense'},
            {'account_code': '5020', 'account_name': 'Rent Expense', 'account_type': 'expense'},
        ]

        for coa_data in chart_of_accounts_data:
            coa, coa_created = ChartOfAccount.objects.get_or_create(
                organization=organization,
                account_code=coa_data['account_code'],
                defaults={
                    'account_name': coa_data['account_name'],
                    'account_type': account_types[coa_data['account_type']],
                    'currency': currency,
                    'allow_manual_journal': True
                }
            )
            if coa_created:
                self.stdout.write(self.style.SUCCESS(f"Chart of Account '{coa.account_name}' created."))
            else:
                self.stdout.write(self.style.NOTICE(f"Chart of Account '{coa.account_name}' already exists."))

        self.stdout.write(self.style.SUCCESS("Test environment setup complete."))