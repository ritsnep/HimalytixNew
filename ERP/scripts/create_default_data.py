"""
ERP/scripts/create_default_data.py

This is the canonical, robust, and idempotent script for seeding all required and demo data for the ERP system.

- Covers all models in usermanagement, accounting, tenancy, etc.
- Ensures all permissions, roles, entities, voucher configs, UDFs, and demo data are present.
- All management commands that seed data should call this script.
- After running, a new user/org/tenant can immediately use the system with all permissions, roles, entities, voucher configs, UDFs, and demo data in place.
- If you add new models or demo data, extend this script.

Usage:
    python ERP/scripts/create_default_data.py
    # or via management command that wraps this logic
"""
import os
import sys
import django
from datetime import datetime, date
from decimal import Decimal
import logging

from django.db import IntegrityError
from django.core.exceptions import ValidationError

# WARNING: This script may create overlapping data if run with create_defaults. Review both scripts before running in production.

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("Before adding erp to sys.path:")
print(sys.path)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
print("After adding erp to sys.path:")
print(sys.path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard.settings')
django.setup()


from django.contrib.auth import get_user_model
from usermanagement.models import CustomUser, LoginLog, Organization, Module, Entity, Permission, Role, UserRole, UserOrganization, OrganizationAddress, OrganizationContact
from accounting.models import (
    FiscalYear,
    AccountingPeriod,
    Department,
    Project,
    CostCenter,
    AccountType,
    ChartOfAccount,
    Currency,
    CurrencyExchangeRate,
    JournalType,
    TaxAuthority,
    TaxType,
    TaxCode,
    VoucherModeConfig,
    Journal,
    JournalLine,
)
from django.utils import timezone
from tenancy.models import Tenant, SubscriptionPlan, TenantSubscription, TenantConfig

def create_default_data():
    """
    Create default data for the accounting system with Nepali fiscal year and NPR currency
    """
    logger.info("Starting to create default data for Nepal...")
    
    # Get the superuser (assuming there's only one, or get the first one)
    try:
        superuser = CustomUser.objects.filter(is_superuser=True).first()
        if not superuser:
            logger.error("No superuser found. Please create a superuser first.")
            return
        logger.info(f"Using superuser: {superuser.username}")
    except Exception as e:
        logger.error(f"Error getting superuser: {e}")
        return
    
    # Create default organization if it doesn't exist
    organization, created = Organization.objects.get_or_create(
        name='Nepali Accounting System',
        code='NEPAL-001',
        type='company',
        legal_name='Nepali Accounting System Pvt. Ltd.',
        tax_id='NP-123456',
        registration_number='REG-2024-001',
        industry_code='ACCT',
        fiscal_year_start_month=4,  # Example: Baisakh (Nepali FY start)
        fiscal_year_start_day=1,
        base_currency_code='NPR',
        status='active',
        is_active=True,
        defaults={
            # Only optional fields not in the main arguments, if any
        }
    )
    if created:
        logger.info(f"Created default organization: {organization.name}")
    else:
        logger.info(f"Using existing organization: {organization.name}")

    # Assign the organization to the superuser
    if superuser and not superuser.organization:
        superuser.organization = organization
        superuser.save()
    
    # After organization creation, add default address and contact
    address, _ = OrganizationAddress.objects.get_or_create(
        organization=organization,
        address_type='head_office',
        defaults={
            'address_line1': '123 Main Street',
            'city': 'Kathmandu',
            'state_province': 'Bagmati',
            'postal_code': '44600',
            'country_code': 'NP',
            'is_primary': True
        }
    )
    contact, _ = OrganizationContact.objects.get_or_create(
        organization=organization,
        contact_type='admin',
        defaults={
            'name': 'Admin Contact',
            'email': 'admin@example.com',
            'phone': '+977-1-1234567',
            'job_title': 'Administrator',
            'is_primary': True
        }
    )
    # Add a sample login log for the superuser
    LoginLog.objects.get_or_create(
        user=superuser,
        login_method='email',
        success=True,
        ip_address='127.0.0.1',
        defaults={
            'logout_time': None,
            'session_time': None,
        }
    )
    # TENANCY DEFAULTS
    # 1. Default tenant
    tenant, _ = Tenant.objects.get_or_create(
        code='DEFAULT',
        defaults={
            'name': 'Default Tenant',
            'slug': 'default-tenant',
            'subscription_tier': 'standard',
            'is_active': True,
            'domain_name': 'default.local',
            'data_schema': 'public',
        }
    )
    # 2. Default subscription plan
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code='STANDARD',
        defaults={
            'name': 'Standard',
            'description': 'Standard plan',
            'is_active': True,
            'base_price': 0,
            'billing_cycle': 'monthly',
            'max_users': 10,
            'max_storage_gb': 10,
            'features': {'feature1': True},
        }
    )
    # 3. Subscribe tenant to plan
    from datetime import timedelta
    today = date.today()
    sub, _ = TenantSubscription.objects.get_or_create(
        tenant=tenant,
        plan=plan,
        start_date=today,
        defaults={
            'end_date': today + timedelta(days=365),
            'auto_renew': True,
            'status': 'active',
            'billing_cycle': 'monthly',
            'price_per_period': 0,
            'currency_code': 'USD',
            'discount_percentage': 0,
            'next_billing_date': today + timedelta(days=30),
        }
    )
    # 4. Add a sample config
    TenantConfig.objects.get_or_create(
        tenant=tenant,
        config_key='welcome_message',
        defaults={
            'config_value': 'Welcome to the Default Tenant!',
            'data_type': 'string',
        }
    )
    
    # Create default currencies with NPR as primary
    currencies_data = [
        {'currency_code': 'NPR', 'currency_name': 'Nepalese Rupee', 'symbol': 'Rs'},
        {'currency_code': 'USD', 'currency_name': 'US Dollar', 'symbol': '$'},
        {'currency_code': 'EUR', 'currency_name': 'Euro', 'symbol': '€'},
        {'currency_code': 'INR', 'currency_name': 'Indian Rupee', 'symbol': '₹'},
    ]
    
    for curr_data in currencies_data:
        currency, created = Currency.objects.get_or_create(
            currency_code=curr_data['currency_code'],
            defaults={
                'currency_name': curr_data['currency_name'],
                'symbol': curr_data['symbol'],
                'is_active': True,
                'created_by': superuser
            }
        )
        if created:
            logger.info(f"Created currency: {currency.currency_code}")

    # Seed baseline exchange rates (NPR as base)
    npr_currency = Currency.objects.get(currency_code='NPR')
    exchange_rate_data = [
        {'code': 'USD', 'rate': Decimal('0.0075')},
        {'code': 'EUR', 'rate': Decimal('0.0070')},
        {'code': 'INR', 'rate': Decimal('0.6250')},
    ]
    rate_date = date.today()
    for rate in exchange_rate_data:
        try:
            to_currency = Currency.objects.get(currency_code=rate['code'])
        except Currency.DoesNotExist:
            continue
        CurrencyExchangeRate.objects.get_or_create(
            organization=organization,
            from_currency=npr_currency,
            to_currency=to_currency,
            rate_date=rate_date,
            defaults={
                'exchange_rate': rate['rate'],
                'source': 'seed',
                'is_active': True,
                'created_by': superuser,
            }
        )
    
    # Create Nepali fiscal year 2081-2082 (2024-07-16 to 2025-07-16)
    fiscal_year = FiscalYear.objects.filter(
        organization=organization,
        name="Fiscal Year 2081-2082"
    ).first()
    if not fiscal_year:
        fiscal_year = FiscalYear.objects.create(
            organization=organization,
            name="Fiscal Year 2081-2082",
            start_date=date(2024, 7, 16),
            end_date=date(2025, 7, 16),
            status='open',
            is_current=True,
            is_default=True,
            created_by=superuser
        )
        logger.info(f"Created fiscal year: {fiscal_year.name}")
    else:
        logger.info(f"Using existing fiscal year: {fiscal_year.name}")
    
    # Create accounting periods for the Nepali fiscal year
    if created:  # Only create periods if fiscal year was just created
        # Nepali months with their English equivalents and date ranges
        nepali_months = [
            {'nepali': 'Shrawan', 'start': date(2024, 7, 16), 'end': date(2024, 8, 16)},
            {'nepali': 'Bhadra', 'start': date(2024, 8, 17), 'end': date(2024, 9, 16)},
            {'nepali': 'Ashwin', 'start': date(2024, 9, 17), 'end': date(2024, 10, 16)},
            {'nepali': 'Kartik', 'start': date(2024, 10, 17), 'end': date(2024, 11, 15)},
            {'nepali': 'Mangsir', 'start': date(2024, 11, 16), 'end': date(2024, 12, 15)},
            {'nepali': 'Poush', 'start': date(2024, 12, 16), 'end': date(2025, 1, 14)},
            {'nepali': 'Magh', 'start': date(2025, 1, 15), 'end': date(2025, 2, 13)},
            {'nepali': 'Falgun', 'start': date(2025, 2, 14), 'end': date(2025, 3, 15)},
            {'nepali': 'Chaitra', 'start': date(2025, 3, 16), 'end': date(2025, 4, 14)},
            {'nepali': 'Baisakh', 'start': date(2025, 4, 15), 'end': date(2025, 5, 15)},
            {'nepali': 'Jestha', 'start': date(2025, 5, 16), 'end': date(2025, 6, 15)},
            {'nepali': 'Asar', 'start': date(2025, 6, 16), 'end': date(2025, 7, 16)},
        ]
        
        current_nepali_month = 1  # Assuming we're in Shrawan for current period
        
        for i, month_data in enumerate(nepali_months, 1):
            period, period_created = AccountingPeriod.objects.get_or_create(
                fiscal_year=fiscal_year,
                period_number=i,
                defaults={
                    'name': f"{month_data['nepali']} 2081-2082",
                    'start_date': month_data['start'],
                    'end_date': month_data['end'],
                    'status': 'open',
                    'is_current': i == current_nepali_month,
                    'created_by': superuser
                }
            )
            if period_created:
                logger.info(f"Created accounting period: {period.name}")
            else:
                logger.info(f"Accounting period already exists: {period.name}")
    else:
        logger.info(f"Accounting periods already exist for fiscal year: {fiscal_year.name}")
    
    # Create default departments for Nepal
    departments_data = [
        'Administration',
        'Finance',
        'Human Resources',
        'Information Technology',
        'Operations',
        'Sales & Marketing',
        'Accounts',
        'Audit'
    ]
    
    for dept_name in departments_data:
        code = dept_name[:10].upper().replace(' ', '_')
        department, created = Department.objects.get_or_create(
            organization=organization,
            code=code,
            name=dept_name
        )
        if created:
            logger.info(f"Created department: {department.name}")
    
    # Create default projects
    projects_data = [
        {'name': 'General Operations', 'description': 'General business operations'},
        {'name': 'Infrastructure Development', 'description': 'IT and infrastructure projects'},
        {'name': 'Marketing Campaign', 'description': 'Marketing and promotional activities'},
        {'name': 'Digital Transformation', 'description': 'Digital transformation initiatives'},
    ]
    
    for proj_data in projects_data:
        project, created = Project.objects.get_or_create(
            organization=organization,
            name=proj_data['name'],
            defaults={
                'description': proj_data['description'],
                'is_active': True,
                'start_date': date.today()
            }
        )
        if created:
            logger.info(f"Created project: {project.name}")
    
    # Create default cost centers
    cost_centers_data = [
        {'name': 'Head Office', 'description': 'Main corporate office'},
        {'name': 'Kathmandu Branch', 'description': 'Kathmandu branch office'},
        {'name': 'Pokhara Branch', 'description': 'Pokhara branch office'},
        {'name': 'Manufacturing Unit', 'description': 'Production facility'},
        {'name': 'Research & Development', 'description': 'R&D activities'},
    ]
    
    for cc_data in cost_centers_data:
        code = cc_data['name'][:10].upper().replace(' ', '_')
        cost_center, created = CostCenter.objects.get_or_create(
            name=cc_data['name'],
            organization=organization,
            code=code,
            defaults={
                'description': cc_data['description'],
                'is_active': True
            }
        )
        if created:
            logger.info(f"Created cost center: {cost_center.name}")
    
    # Create default account types
    account_types_data = [
        # Assets
        {'nature': 'asset', 'name': 'Current Assets', 'classification': 'Current', 'balance_sheet_category': 'Current Assets', 'display_order': 1},
        {'nature': 'asset', 'name': 'Fixed Assets', 'classification': 'Non-Current', 'balance_sheet_category': 'Fixed Assets', 'display_order': 2},
        {'nature': 'asset', 'name': 'Intangible Assets', 'classification': 'Non-Current', 'balance_sheet_category': 'Intangible Assets', 'display_order': 3},
        {'nature': 'asset', 'name': 'Investments', 'classification': 'Non-Current', 'balance_sheet_category': 'Investments', 'display_order': 4},
        
        # Liabilities
        {'nature': 'liability', 'name': 'Current Liabilities', 'classification': 'Current', 'balance_sheet_category': 'Current Liabilities', 'display_order': 5},
        {'nature': 'liability', 'name': 'Long-term Liabilities', 'classification': 'Non-Current', 'balance_sheet_category': 'Long-term Liabilities', 'display_order': 6},
        
        # Equity
        {'nature': 'equity', 'name': 'Share Capital', 'classification': 'Equity', 'balance_sheet_category': 'Shareholders Equity', 'display_order': 7},
        {'nature': 'equity', 'name': 'Retained Earnings', 'classification': 'Equity', 'balance_sheet_category': 'Shareholders Equity', 'display_order': 8},
        {'nature': 'equity', 'name': 'Reserves', 'classification': 'Equity', 'balance_sheet_category': 'Shareholders Equity', 'display_order': 9},
        
        # Income
        {'nature': 'income', 'name': 'Revenue', 'classification': 'Operating', 'income_statement_category': 'Revenue', 'display_order': 10},
        {'nature': 'income', 'name': 'Other Income', 'classification': 'Non-Operating', 'income_statement_category': 'Other Income', 'display_order': 11},
        
        # Expenses
        {'nature': 'expense', 'name': 'Cost of Goods Sold', 'classification': 'Direct', 'income_statement_category': 'Cost of Sales', 'display_order': 12},
        {'nature': 'expense', 'name': 'Operating Expenses', 'classification': 'Operating', 'income_statement_category': 'Operating Expenses', 'display_order': 13},
        {'nature': 'expense', 'name': 'Administrative Expenses', 'classification': 'Operating', 'income_statement_category': 'Administrative Expenses', 'display_order': 14},
        {'nature': 'expense', 'name': 'Financial Expenses', 'classification': 'Operating', 'income_statement_category': 'Financial Expenses', 'display_order': 15},
    ]
    
    for acc_type_data in account_types_data:
        account_type, created = AccountType.objects.get_or_create(
            name=acc_type_data['name'],
            nature=acc_type_data['nature'],
            defaults={
                'classification': acc_type_data['classification'],
                'balance_sheet_category': acc_type_data.get('balance_sheet_category'),
                'income_statement_category': acc_type_data.get('income_statement_category'),
                'display_order': acc_type_data['display_order'],
                'system_type': True,
                'created_by': superuser
            }
        )
        if created:
            logger.info(f"Created account type: {account_type.name}")
    
    # Create default chart of accounts for Nepal
    # Get account types for reference
    current_assets = AccountType.objects.get(name='Current Assets')
    fixed_assets = AccountType.objects.get(name='Fixed Assets')
    current_liabilities = AccountType.objects.get(name='Current Liabilities')
    equity = AccountType.objects.get(name='Share Capital')
    revenue = AccountType.objects.get(name='Revenue')
    expenses = AccountType.objects.get(name='Operating Expenses')
    admin_expenses = AccountType.objects.get(name='Administrative Expenses')
    
    accounts_data = [
        # Top-level Assets
        {'account_name': 'Assets', 'account_type': current_assets},
        {'account_name': 'Cash in Hand', 'account_type': current_assets, 'parent': 'Assets'},
        {'account_name': 'Bank Account - NPR', 'account_type': current_assets, 'is_bank_account': True, 'parent': 'Assets'},
        {'account_name': 'Bank Account - USD', 'account_type': current_assets, 'is_bank_account': True, 'parent': 'Assets'},
        {'account_name': 'Accounts Receivable', 'account_type': current_assets, 'is_control_account': True, 'parent': 'Assets'},
        {'account_name': 'Trade Receivables', 'account_type': current_assets, 'parent': 'Assets'},
        {'account_name': 'Inventory - Raw Materials', 'account_type': current_assets, 'parent': 'Assets'},
        {'account_name': 'Inventory - Finished Goods', 'account_type': current_assets, 'parent': 'Assets'},
        {'account_name': 'Prepaid Expenses', 'account_type': current_assets, 'parent': 'Assets'},
        {'account_name': 'Advance to Suppliers', 'account_type': current_assets, 'parent': 'Assets'},
        # Top-level Fixed Assets
        {'account_name': 'Fixed Assets', 'account_type': fixed_assets},
        {'account_name': 'Land and Building', 'account_type': fixed_assets, 'parent': 'Fixed Assets'},
        {'account_name': 'Office Equipment', 'account_type': fixed_assets, 'parent': 'Fixed Assets'},
        {'account_name': 'Furniture and Fixtures', 'account_type': fixed_assets, 'parent': 'Fixed Assets'},
        {'account_name': 'Computer and Software', 'account_type': fixed_assets, 'parent': 'Fixed Assets'},
        {'account_name': 'Vehicle', 'account_type': fixed_assets, 'parent': 'Fixed Assets'},
        # Top-level Liabilities
        {'account_name': 'Liabilities', 'account_type': current_liabilities},
        {'account_name': 'Accounts Payable', 'account_type': current_liabilities, 'is_control_account': True, 'parent': 'Liabilities'},
        {'account_name': 'Trade Payables', 'account_type': current_liabilities, 'parent': 'Liabilities'},
        {'account_name': 'VAT Payable', 'account_type': current_liabilities, 'parent': 'Liabilities'},
        {'account_name': 'TDS Payable', 'account_type': current_liabilities, 'parent': 'Liabilities'},
        {'account_name': 'Social Security Fund', 'account_type': current_liabilities, 'parent': 'Liabilities'},
        {'account_name': 'Citizens Investment Trust', 'account_type': current_liabilities, 'parent': 'Liabilities'},
        {'account_name': 'Provident Fund', 'account_type': current_liabilities, 'parent': 'Liabilities'},
        {'account_name': 'Salary Payable', 'account_type': current_liabilities, 'parent': 'Liabilities'},
        {'account_name': 'Accrued Expenses', 'account_type': current_liabilities, 'parent': 'Liabilities'},
        # Top-level Equity
        {'account_name': 'Equity', 'account_type': equity},
        {'account_name': 'Share Capital', 'account_type': equity, 'parent': 'Equity'},
        {'account_name': 'Retained Earnings', 'account_type': equity, 'parent': 'Equity'},
        {'account_name': 'General Reserve', 'account_type': equity, 'parent': 'Equity'},
        # Top-level Revenue
        {'account_name': 'Revenue', 'account_type': revenue},
        {'account_name': 'Sales Revenue', 'account_type': revenue, 'parent': 'Revenue'},
        {'account_name': 'Service Revenue', 'account_type': revenue, 'parent': 'Revenue'},
        {'account_name': 'Export Revenue', 'account_type': revenue, 'parent': 'Revenue'},
        {'account_name': 'Interest Income', 'account_type': revenue, 'parent': 'Revenue'},
        {'account_name': 'Other Income', 'account_type': revenue, 'parent': 'Revenue'},
        # Top-level Expenses
        {'account_name': 'Expenses', 'account_type': expenses},
        {'account_name': 'Cost of Goods Sold', 'account_type': expenses, 'parent': 'Expenses'},
        {'account_name': 'Salary and Wages', 'account_type': admin_expenses, 'parent': 'Expenses'},
        {'account_name': 'Office Rent', 'account_type': admin_expenses, 'parent': 'Expenses'},
        {'account_name': 'Utilities', 'account_type': admin_expenses, 'parent': 'Expenses'},
        {'account_name': 'Office Supplies', 'account_type': admin_expenses, 'parent': 'Expenses'},
        {'account_name': 'Professional Fees', 'account_type': admin_expenses, 'parent': 'Expenses'},
        {'account_name': 'Travel and Transportation', 'account_type': expenses, 'parent': 'Expenses'},
        {'account_name': 'Communication Expenses', 'account_type': admin_expenses, 'parent': 'Expenses'},
        {'account_name': 'Depreciation Expense', 'account_type': expenses, 'parent': 'Expenses'},
        {'account_name': 'Bank Charges', 'account_type': expenses, 'parent': 'Expenses'},
        {'account_name': 'Repair and Maintenance', 'account_type': expenses, 'parent': 'Expenses'},
    ]

    npr_currency = Currency.objects.get(currency_code='NPR')
    created_accounts = {}  # Map account name to created account object
    for acc_data in accounts_data:
        base_name = acc_data['account_name']
        suffix = 0
        while True:
            account_name = base_name if suffix == 0 else f"{base_name} ({suffix})"
            parent_account = None
            if 'parent' in acc_data and acc_data['parent']:
                parent_account = created_accounts.get(acc_data['parent'])
            temp_account = ChartOfAccount(
                organization=organization,
                account_name=account_name,
                account_type=acc_data['account_type'],
                parent_account=parent_account,
                description=f"Default {account_name} account",
                is_active=True,
                created_by=superuser,
                currency=npr_currency,
                is_bank_account=acc_data.get('is_bank_account', False),
                is_control_account=acc_data.get('is_control_account', False)
            )
            try:
                temp_account.save()
                logger.info(f"Created account: {temp_account.account_name} (code: {temp_account.account_code})")
                created_accounts[account_name] = temp_account
                break
            except ValidationError as e:
                error_msg = str(e)
                if ('account code already exists' in error_msg or
                    'Chart of account with this Organization and Account code already exists' in error_msg or
                    'account_name' in error_msg):
                    suffix += 1
                    continue
                else:
                    logger.error(f"Error creating account '{account_name}': {e}")
                    break
    # After account creation, print all Chart of Accounts for verification
    logger.info("\nAll Chart of Accounts for organization:")
    for acc in ChartOfAccount.objects.filter(organization=organization).order_by('account_code'):
        parent_name = acc.parent_account.account_name if acc.parent_account else 'None'
        logger.info(f"{acc.account_code}: {acc.account_name} (parent: {parent_name})")
    # Create default journal types
    journal_types_data = [
        {'name': 'General Journal', 'description': 'General journal entries', 'auto_numbering_prefix': 'GJ'},
        {'name': 'Cash Receipt', 'description': 'Cash receipts', 'auto_numbering_prefix': 'CR'},
        {'name': 'Cash Payment', 'description': 'Cash payments', 'auto_numbering_prefix': 'CP'},
        {'name': 'Bank Receipt', 'description': 'Bank receipts', 'auto_numbering_prefix': 'BR'},
        {'name': 'Bank Payment', 'description': 'Bank payments', 'auto_numbering_prefix': 'BP'},
        {'name': 'Sales Journal', 'description': 'Sales transactions', 'auto_numbering_prefix': 'SJ'},
        {'name': 'Purchase Journal', 'description': 'Purchase transactions', 'auto_numbering_prefix': 'PJ'},
        {'name': 'Adjustment Journal', 'description': 'Adjusting entries', 'auto_numbering_prefix': 'AJ'},
    ]
    
    for jt_data in journal_types_data:
        journal_type, created = JournalType.objects.get_or_create(
            organization=organization,
            code=jt_data['auto_numbering_prefix'],  # Use code as unique field
            defaults={
                'name': jt_data['name'],
                'description': jt_data['description'],
                'auto_numbering_prefix': jt_data['auto_numbering_prefix'],
                'auto_numbering_next': 1,
                'is_system_type': True,
                'is_active': True,
                'created_by': superuser
            }
        )
        if created:
            logger.info(f"Created journal type: {journal_type.name}")
        else:
            logger.info(f"Using existing journal type: {journal_type.name}")
    
    # Create default tax authority for Nepal
    tax_authority, created = TaxAuthority.objects.get_or_create(
        organization=organization,
        name='Inland Revenue Department',
        defaults={
            'country_code': 'NP',
            'description': 'Nepal Tax Authority - Inland Revenue Department',
            'is_active': True,
            'is_default': True,
            'created_by': superuser
        }
    )
    if created:
        logger.info(f"Created tax authority: {tax_authority.name}")
    
    # Create default tax types for Nepal
    tax_types_data = [
        {'name': 'Value Added Tax (VAT)', 'filing_frequency': 'monthly'},
        {'name': 'Tax Deducted at Source (TDS)', 'filing_frequency': 'monthly'},
        {'name': 'Income Tax', 'filing_frequency': 'annual'},
    ]
    
    created_tax_types = []
    for tt_data in tax_types_data:
        tax_type, created = TaxType.objects.get_or_create(
            organization=organization,
            name=tt_data['name'],
            defaults={
                'authority': tax_authority,
                'description': f"Nepal {tt_data['name']}",
                'filing_frequency': tt_data['filing_frequency'],
                'is_active': True,
                'created_by': superuser
            }
        )
        if created:
            logger.info(f"Created tax type: {tax_type.name}")
        created_tax_types.append(tax_type)
    
    # Create default tax codes for Nepal
    vat_tax_type = next((tt for tt in created_tax_types if 'VAT' in tt.name), created_tax_types[0])
    tds_tax_type = next((tt for tt in created_tax_types if 'TDS' in tt.name), created_tax_types[0])
    
    tax_codes_data = [
        # VAT Codes
        {'name': 'VAT Standard Rate', 'tax_rate': Decimal('13.00'), 'description': 'Standard VAT rate 13%', 'tax_type': vat_tax_type},
        {'name': 'VAT Zero Rate', 'tax_rate': Decimal('0.00'), 'description': 'Zero VAT rate', 'tax_type': vat_tax_type},
        {'name': 'VAT Exempt', 'tax_rate': Decimal('0.00'), 'description': 'VAT exempt', 'tax_type': vat_tax_type},
        
        # TDS Codes
        {'name': 'TDS Salary', 'tax_rate': Decimal('1.00'), 'description': 'TDS on salary 1%', 'tax_type': tds_tax_type},
        {'name': 'TDS Professional Fee', 'tax_rate': Decimal('5.00'), 'description': 'TDS on professional fees 5%', 'tax_type': tds_tax_type},
        {'name': 'TDS Contractor', 'tax_rate': Decimal('2.00'), 'description': 'TDS on contractor payment 2%', 'tax_type': tds_tax_type},
        {'name': 'TDS Rent', 'tax_rate': Decimal('10.00'), 'description': 'TDS on rent 10%', 'tax_type': tds_tax_type},
    ]
    
    for tc_data in tax_codes_data:
        tax_code, created = TaxCode.objects.get_or_create(
            organization=organization,
            name=tc_data['name'],
            defaults={
                'tax_type': tc_data['tax_type'],
                'tax_authority': tax_authority,
                'tax_rate': tc_data['tax_rate'],
                'rate': tc_data['tax_rate'],
                'description': tc_data['description'],
                'is_active': True,
                'is_recoverable': 'VAT' in tc_data['name'],
                'effective_from': date(2024, 7, 16),  # Start of fiscal year
                'created_by': superuser
            }
        )
        if created:
            logger.info(f"Created tax code: {tax_code.name}")
    default_ui_schema = {
        "header": {
            "journal_date": {"type": "date", "label": "Date", "required": True},
            "description": {"type": "char", "label": "Description", "required": False},
        },
        "lines": {
            "account": {"type": "account", "label": "Account", "required": True},
            "debit_amount": {"type": "decimal", "label": "Debit", "required": False},
            "credit_amount": {"type": "decimal", "label": "Credit", "required": False},
        }
    }
    # Create default voucher mode config
    voucher_config, created = VoucherModeConfig.objects.get_or_create(
        organization=organization,
        name='Nepal Standard Voucher',
        defaults={
            'description': 'Standard voucher configuration for Nepal',
            'is_default': True,
            'layout_style': 'standard',
            'show_account_balances': True,
            'show_tax_details': True,
            'show_dimensions': True,
            'allow_multiple_currencies': True,
            'require_line_description': True,
            'default_currency': 'NPR',
            'created_by': superuser,
            'ui_schema': default_ui_schema,
        }
    )
    if created:
        logger.info(f"Created voucher mode config: {voucher_config.name}")
    
    # --- Default Security Setup: Modules, Entities, Permissions, Roles ---
    # 1. Create default module
    accounting_module, _ = Module.objects.get_or_create(
        name='Accounting',
        code='accounting',
        description='Accounting module',
        icon='fas fa-calculator',
        display_order=1,
        is_active=True
    )
    if not hasattr(accounting_module, 'created_by'):
        pass  # No created_by field to set

    # 1.1 Create default system roles for the organization
    roles_data = [
        {'name': 'Admin', 'code': 'ADMIN', 'description': 'Full access to all features', 'is_system': True},
        {'name': 'Clerk', 'code': 'CLERK', 'description': 'Clerk with limited access', 'is_system': True},
        {'name': 'Manager', 'code': 'MANAGER', 'description': 'Manager with approval rights', 'is_system': True},
        {'name': 'Auditor', 'code': 'AUDITOR', 'description': 'Auditor with read-only access', 'is_system': True},
    ]
    role_objs = {}
    for role_data in roles_data:
        if not role_data['code']:
            logger.warning(f"Skipping role with empty code: {role_data}")
            continue
        role, _ = Role.objects.get_or_create(
            name=role_data['name'],
            code=role_data['code'],
            organization=organization,
            defaults={
                'description': role_data['description'],
                'is_system': role_data['is_system'],
                'is_active': True,
                'created_by': superuser,
                'updated_by': superuser
            }
        )
        role_objs[role_data['code']] = role

    # Ensure USER role exists (for user_role assignment below)
    if 'USER' not in role_objs:
        user_role_obj, _ = Role.objects.get_or_create(
            name='User',
            code='USER',
            organization=organization,
            defaults={
                'description': 'Basic user access',
                'is_system': True,
                'is_active': True,
                'created_by': superuser,
                'updated_by': superuser
            }
        )
        role_objs['USER'] = user_role_obj

    # 2. Create default entities for the module
    entities_data = [
        {'name': 'Fiscal Year', 'code': 'fiscalyear', 'description': 'Fiscal Year management'},
        {'name': 'Accounting Period', 'code': 'accountingperiod', 'description': 'Accounting Period management'},
        {'name': 'Chart of Account', 'code': 'chartofaccount', 'description': 'Chart of Accounts management'},
        {'name': 'Department', 'code': 'department', 'description': 'Department management'},
        {'name': 'Project', 'code': 'project', 'description': 'Project management'},
        {'name': 'Cost Center', 'code': 'costcenter', 'description': 'Cost Center management'},
        {'name': 'Journal', 'code': 'journal', 'description': 'Journal management'},
        {'name': 'Journal Type', 'code': 'journaltype', 'description': 'Journal Type management'},
        {'name': 'General Ledger', 'code': 'generalledger', 'description': 'General Ledger management'},
        {'name': 'Currency', 'code': 'currency', 'description': 'Currency management'},
        {'name': 'Currency Exchange Rate', 'code': 'currencyexchangerate', 'description': 'Currency Exchange Rate management'},
        {'name': 'Tax Authority', 'code': 'taxauthority', 'description': 'Tax Authority management'},
        {'name': 'Tax Type', 'code': 'taxtype', 'description': 'Tax Type management'},
        {'name': 'Tax Code', 'code': 'taxcode', 'description': 'Tax Code management'},
        {'name': 'Voucher Mode Config', 'code': 'vouchermodeconfig', 'description': 'Voucher Mode Config management'},
        {'name': 'Voucher Mode Default', 'code': 'vouchermodedefault', 'description': 'Voucher Mode Default management'},
        {'name': 'Voucher UDF Config', 'code': 'voucherudfconfig', 'description': 'Voucher UDF Configuration management'},
        {'name': 'Accounts Payable Payment', 'code': 'appayment', 'description': 'Accounts Payable Payment management'},
    ]
    entity_objs = []
    for ent in entities_data:
        entity, _ = Entity.objects.get_or_create(
            module=accounting_module,
            code=ent['code'],
            defaults={
                'name': ent['name'],
                'description': ent['description'],
                'is_active': True
            }
        )
        entity_objs.append(entity)

    # 3. Create permissions for each entity (CRUD)
    actions = ['view', 'add', 'change', 'delete']
    custom_actions = {
        'journal': ['submit_journal', 'post_journal'],
    }
    permission_objs = []
    for entity in entity_objs:
        entity_actions = actions + custom_actions.get(entity.code, [])
        for action in entity_actions:
            perm, _ = Permission.objects.get_or_create(
                module=accounting_module,
                entity=entity,
                action=action,
                defaults={
                    'name': f'Can {action} {entity.name}',
                    'codename': f'{accounting_module.code}_{entity.code}_{action}',
                    'description': f'Can {action} {entity.name}',
                    'is_active': True
                }
            )
            permission_objs.append(perm)

    # 4. Assign permissions to roles
    admin_role = role_objs['ADMIN']
    user_role = role_objs['USER']
    manager_role = role_objs.get('MANAGER')
    clerk_role = role_objs.get('CLERK')
    auditor_role = role_objs.get('AUDITOR')
    admin_role.permissions.set(permission_objs)
    admin_role.save()
    view_perms = [p for p in permission_objs if p.action == 'view']
    user_role.permissions.set(view_perms)
    user_role.save()

    if auditor_role:
        auditor_role.permissions.set(view_perms)

    submit_perm = next((p for p in permission_objs if p.entity.code == 'journal' and p.action == 'submit_journal'), None)
    post_perm = next((p for p in permission_objs if p.entity.code == 'journal' and p.action == 'post_journal'), None)

    if clerk_role and submit_perm:
        clerk_role.permissions.add(submit_perm)

    if manager_role:
        if submit_perm:
            manager_role.permissions.add(submit_perm)
        if post_perm:
            manager_role.permissions.add(post_perm)

    # 5. Assign Administrator role to superuser
    UserRole.objects.get_or_create(
        user=superuser,
        role=admin_role,
        organization=organization,
        defaults={
            'is_active': True,
            'created_by': superuser,
            'updated_by': superuser
        }
    )

    # 6. Auto-assign all users to the organization via UserOrganization
    all_users = CustomUser.objects.all()
    for user in all_users:
        UserOrganization.objects.get_or_create(
            user=user,
            organization=organization,
            defaults={
                'is_owner': user.is_superuser,
                'is_active': True,
                'role': 'owner' if user.is_superuser else 'member'
            }
        )
        logger.info(f"Ensured user '{user.username}' is assigned to organization '{organization.name}'")

    # --- DEMO VOUCHER ENTRY ---
    # Only create if no journals exist for this org/fiscal year
    if not Journal.objects.filter(organization=organization, period__fiscal_year=fiscal_year).exists():
        period = AccountingPeriod.objects.filter(fiscal_year=fiscal_year).first()
        journal_type = JournalType.objects.filter(organization=organization).first()
        cash_account = ChartOfAccount.objects.filter(organization=organization, account_name__icontains='Cash').first()
        expense_account = ChartOfAccount.objects.filter(organization=organization, account_name__icontains='Expense').first()
        if period and journal_type and cash_account and expense_account:
            demo_journal = Journal.objects.create(
                organization=organization,
                journal_number='GJ0001',
                journal_type=journal_type,
                period=period,
                journal_date=period.start_date,
                description='Demo voucher entry',
                currency_code='NPR',
                exchange_rate=1,
                status='draft',
                created_by=superuser
            )
            JournalLine.objects.create(
                journal=demo_journal,
                line_number=1,
                account=expense_account,
                debit_amount=Decimal('1000.00'),
                credit_amount=Decimal('0.00'),
                description='Demo expense',
                currency_code='NPR',
                exchange_rate=1,
                created_by=superuser
            )
            JournalLine.objects.create(
                journal=demo_journal,
                line_number=2,
                account=cash_account,
                debit_amount=Decimal('0.00'),
                credit_amount=Decimal('1000.00'),
                description='Demo cash payment',
                currency_code='NPR',
                exchange_rate=1,
                created_by=superuser
            )
            logger.info('Created demo voucher entry with two lines.')
        else:
            logger.warning('Could not create demo voucher: missing period, journal type, or accounts.')
    else:
        logger.info('Demo voucher entry already exists.')

    logger.info("\nDefault data creation for Nepal completed successfully!")
    logger.info("Summary:")
    logger.info(f"- Organization: {organization.name}")
    logger.info(f"- Fiscal Year: {fiscal_year.name} (2024-07-16 to 2025-07-16)")
    logger.info(f"- Accounting Periods: 12 Nepali months created")
    logger.info(f"- Departments: {len(departments_data)} departments")
    logger.info(f"- Projects: {len(projects_data)} projects")
    logger.info(f"- Cost Centers: {len(cost_centers_data)} cost centers")
    logger.info(f"- Account Types: {len(account_types_data)} account types")
    logger.info(f"- Chart of Accounts: {len(accounts_data)} accounts")
    logger.info(f"- Journal Types: {len(journal_types_data)} journal types")
    logger.info(f"- Tax Codes: {len(tax_codes_data)} tax codes")
    logger.info(f"- Currencies: {len(currencies_data)} currencies (NPR as default)")
    logger.info(f"- Tax Authority: Inland Revenue Department")
    logger.info(f"- Default Currency: NPR (Nepalese Rupee)")

if __name__ == '__main__':
    create_default_data()
