"""
ERP/scripts/seed_database.py

COMPREHENSIVE DATABASE SEED SCRIPT
===================================
This is the canonical, idempotent script for seeding all required data for a fresh ERP database setup.

Covers all apps:
- usermanagement: Organization, Modules, Entities, Permissions, Roles, Users
- tenancy: Tenant, SubscriptionPlan, TenantSubscription, TenantConfig
- accounting: FiscalYear, AccountingPeriod, AccountType, ChartOfAccount, Currency, 
              JournalType, TaxAuthority, TaxType, TaxCode, VoucherModeConfig, 
              Department, Project, CostCenter, PaymentTerm, Vendor
- inventory: ProductCategory, Product, Warehouse, Location
- billing: SubscriptionPlan (billing module)
- service_management: DeviceCategory, DeviceModel
- lpg_vertical: LpgProduct, CylinderType

Usage:
    python manage.py shell
    >>> from scripts.seed_database import seed_all
    >>> seed_all()

    OR via management command:
    python manage.py seed_database
"""
import os
import sys
import logging
from datetime import date, timedelta
from decimal import Decimal

import django

# Setup Django if running standalone
if not django.conf.settings.configured:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard.settings')
    django.setup()

from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils import timezone

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

User = get_user_model()


# =============================================================================
# CONFIGURATION CONSTANTS
# =============================================================================

# Nepal-specific fiscal year (Nepali calendar 2082-2083)
FISCAL_YEAR_START = date(2025, 7, 15)  # Shrawan 1, 2082
FISCAL_YEAR_END = date(2026, 7, 15)    # Asar 31, 2083

NEPALI_MONTHS = [
    {'nepali': 'Shrawan', 'start': date(2025, 7, 15), 'end': date(2025, 8, 15)},
    {'nepali': 'Bhadra', 'start': date(2025, 8, 16), 'end': date(2025, 9, 15)},
    {'nepali': 'Ashwin', 'start': date(2025, 9, 16), 'end': date(2025, 10, 15)},
    {'nepali': 'Kartik', 'start': date(2025, 10, 16), 'end': date(2025, 11, 14)},
    {'nepali': 'Mangsir', 'start': date(2025, 11, 15), 'end': date(2025, 12, 14)},
    {'nepali': 'Poush', 'start': date(2025, 12, 15), 'end': date(2026, 1, 13)},
    {'nepali': 'Magh', 'start': date(2026, 1, 14), 'end': date(2026, 2, 12)},
    {'nepali': 'Falgun', 'start': date(2026, 2, 13), 'end': date(2026, 3, 14)},
    {'nepali': 'Chaitra', 'start': date(2026, 3, 15), 'end': date(2026, 4, 13)},
    {'nepali': 'Baisakh', 'start': date(2026, 4, 14), 'end': date(2026, 5, 14)},
    {'nepali': 'Jestha', 'start': date(2026, 5, 15), 'end': date(2026, 6, 13)},
    {'nepali': 'Asar', 'start': date(2026, 6, 14), 'end': date(2026, 7, 15)},
]

CURRENCIES = [
    {'code': 'NPR', 'name': 'Nepalese Rupee', 'symbol': 'Rs'},
    {'code': 'USD', 'name': 'US Dollar', 'symbol': '$'},
    {'code': 'EUR', 'name': 'Euro', 'symbol': '€'},
    {'code': 'INR', 'name': 'Indian Rupee', 'symbol': '₹'},
    {'code': 'GBP', 'name': 'British Pound', 'symbol': '£'},
]

EXCHANGE_RATES = [
    {'from': 'NPR', 'to': 'USD', 'rate': Decimal('0.0075')},
    {'from': 'NPR', 'to': 'EUR', 'rate': Decimal('0.0070')},
    {'from': 'NPR', 'to': 'INR', 'rate': Decimal('0.6250')},
    {'from': 'NPR', 'to': 'GBP', 'rate': Decimal('0.0060')},
]

ACCOUNT_TYPES = [
    # Assets
    {'nature': 'asset', 'name': 'Current Assets', 'classification': 'Current', 'bs_category': 'Current Assets', 'order': 1},
    {'nature': 'asset', 'name': 'Fixed Assets', 'classification': 'Non-Current', 'bs_category': 'Fixed Assets', 'order': 2},
    {'nature': 'asset', 'name': 'Intangible Assets', 'classification': 'Non-Current', 'bs_category': 'Intangible Assets', 'order': 3},
    {'nature': 'asset', 'name': 'Investments', 'classification': 'Non-Current', 'bs_category': 'Investments', 'order': 4},
    # Liabilities
    {'nature': 'liability', 'name': 'Current Liabilities', 'classification': 'Current', 'bs_category': 'Current Liabilities', 'order': 5},
    {'nature': 'liability', 'name': 'Long-term Liabilities', 'classification': 'Non-Current', 'bs_category': 'Long-term Liabilities', 'order': 6},
    # Equity
    {'nature': 'equity', 'name': 'Share Capital', 'classification': 'Equity', 'bs_category': 'Shareholders Equity', 'order': 7},
    {'nature': 'equity', 'name': 'Retained Earnings', 'classification': 'Equity', 'bs_category': 'Shareholders Equity', 'order': 8},
    {'nature': 'equity', 'name': 'Reserves', 'classification': 'Equity', 'bs_category': 'Shareholders Equity', 'order': 9},
    # Income
    {'nature': 'income', 'name': 'Revenue', 'classification': 'Operating', 'is_category': 'Revenue', 'order': 10},
    {'nature': 'income', 'name': 'Other Income', 'classification': 'Non-Operating', 'is_category': 'Other Income', 'order': 11},
    # Expenses
    {'nature': 'expense', 'name': 'Cost of Goods Sold', 'classification': 'Direct', 'is_category': 'Cost of Sales', 'order': 12},
    {'nature': 'expense', 'name': 'Operating Expenses', 'classification': 'Operating', 'is_category': 'Operating Expenses', 'order': 13},
    {'nature': 'expense', 'name': 'Administrative Expenses', 'classification': 'Operating', 'is_category': 'Administrative Expenses', 'order': 14},
    {'nature': 'expense', 'name': 'Financial Expenses', 'classification': 'Operating', 'is_category': 'Financial Expenses', 'order': 15},
]

CHART_OF_ACCOUNTS = [
    # Assets
    {'code': '1000', 'name': 'Assets', 'type': 'Current Assets', 'parent': None},
    {'code': '1010', 'name': 'Cash in Hand', 'type': 'Current Assets', 'parent': '1000'},
    {'code': '1020', 'name': 'Bank Account - NPR', 'type': 'Current Assets', 'parent': '1000', 'is_bank': True},
    {'code': '1021', 'name': 'Bank Account - USD', 'type': 'Current Assets', 'parent': '1000', 'is_bank': True},
    {'code': '1100', 'name': 'Accounts Receivable', 'type': 'Current Assets', 'parent': '1000', 'is_control': True},
    {'code': '1110', 'name': 'Trade Receivables', 'type': 'Current Assets', 'parent': '1100'},
    {'code': '1200', 'name': 'Inventory - Raw Materials', 'type': 'Current Assets', 'parent': '1000'},
    {'code': '1210', 'name': 'Inventory - Finished Goods', 'type': 'Current Assets', 'parent': '1000'},
    {'code': '1300', 'name': 'Prepaid Expenses', 'type': 'Current Assets', 'parent': '1000'},
    {'code': '1310', 'name': 'Advance to Suppliers', 'type': 'Current Assets', 'parent': '1000'},
    # Fixed Assets
    {'code': '1500', 'name': 'Fixed Assets', 'type': 'Fixed Assets', 'parent': None},
    {'code': '1510', 'name': 'Land and Building', 'type': 'Fixed Assets', 'parent': '1500'},
    {'code': '1520', 'name': 'Office Equipment', 'type': 'Fixed Assets', 'parent': '1500'},
    {'code': '1530', 'name': 'Furniture and Fixtures', 'type': 'Fixed Assets', 'parent': '1500'},
    {'code': '1540', 'name': 'Computer and Software', 'type': 'Fixed Assets', 'parent': '1500'},
    {'code': '1550', 'name': 'Vehicle', 'type': 'Fixed Assets', 'parent': '1500'},
    {'code': '1600', 'name': 'Accumulated Depreciation', 'type': 'Fixed Assets', 'parent': '1500'},
    # Liabilities
    {'code': '2000', 'name': 'Liabilities', 'type': 'Current Liabilities', 'parent': None},
    {'code': '2010', 'name': 'Accounts Payable', 'type': 'Current Liabilities', 'parent': '2000', 'is_control': True},
    {'code': '2020', 'name': 'Trade Payables', 'type': 'Current Liabilities', 'parent': '2010'},
    {'code': '2100', 'name': 'VAT Payable', 'type': 'Current Liabilities', 'parent': '2000'},
    {'code': '2110', 'name': 'TDS Payable', 'type': 'Current Liabilities', 'parent': '2000'},
    {'code': '2120', 'name': 'Social Security Fund', 'type': 'Current Liabilities', 'parent': '2000'},
    {'code': '2130', 'name': 'Citizens Investment Trust', 'type': 'Current Liabilities', 'parent': '2000'},
    {'code': '2140', 'name': 'Provident Fund', 'type': 'Current Liabilities', 'parent': '2000'},
    {'code': '2200', 'name': 'Salary Payable', 'type': 'Current Liabilities', 'parent': '2000'},
    {'code': '2210', 'name': 'Accrued Expenses', 'type': 'Current Liabilities', 'parent': '2000'},
    {'code': '2500', 'name': 'Long-term Loans', 'type': 'Long-term Liabilities', 'parent': None},
    # Equity
    {'code': '3000', 'name': 'Equity', 'type': 'Share Capital', 'parent': None},
    {'code': '3010', 'name': 'Share Capital', 'type': 'Share Capital', 'parent': '3000'},
    {'code': '3100', 'name': 'Retained Earnings', 'type': 'Retained Earnings', 'parent': '3000'},
    {'code': '3200', 'name': 'General Reserve', 'type': 'Reserves', 'parent': '3000'},
    {'code': '3300', 'name': 'Current Year Profit/Loss', 'type': 'Retained Earnings', 'parent': '3000'},
    # Revenue
    {'code': '4000', 'name': 'Revenue', 'type': 'Revenue', 'parent': None},
    {'code': '4010', 'name': 'Sales Revenue', 'type': 'Revenue', 'parent': '4000'},
    {'code': '4020', 'name': 'Service Revenue', 'type': 'Revenue', 'parent': '4000'},
    {'code': '4030', 'name': 'Export Revenue', 'type': 'Revenue', 'parent': '4000'},
    {'code': '4100', 'name': 'Interest Income', 'type': 'Other Income', 'parent': None},
    {'code': '4200', 'name': 'Other Income', 'type': 'Other Income', 'parent': None},
    # Expenses
    {'code': '5000', 'name': 'Expenses', 'type': 'Operating Expenses', 'parent': None},
    {'code': '5010', 'name': 'Cost of Goods Sold', 'type': 'Cost of Goods Sold', 'parent': '5000'},
    {'code': '5100', 'name': 'Salary and Wages', 'type': 'Administrative Expenses', 'parent': '5000'},
    {'code': '5110', 'name': 'Office Rent', 'type': 'Administrative Expenses', 'parent': '5000'},
    {'code': '5120', 'name': 'Utilities', 'type': 'Administrative Expenses', 'parent': '5000'},
    {'code': '5130', 'name': 'Office Supplies', 'type': 'Administrative Expenses', 'parent': '5000'},
    {'code': '5140', 'name': 'Professional Fees', 'type': 'Administrative Expenses', 'parent': '5000'},
    {'code': '5150', 'name': 'Travel and Transportation', 'type': 'Operating Expenses', 'parent': '5000'},
    {'code': '5160', 'name': 'Communication Expenses', 'type': 'Administrative Expenses', 'parent': '5000'},
    {'code': '5170', 'name': 'Depreciation Expense', 'type': 'Operating Expenses', 'parent': '5000'},
    {'code': '5180', 'name': 'Bank Charges', 'type': 'Financial Expenses', 'parent': '5000'},
    {'code': '5190', 'name': 'Repair and Maintenance', 'type': 'Operating Expenses', 'parent': '5000'},
    {'code': '5200', 'name': 'Interest Expense', 'type': 'Financial Expenses', 'parent': '5000'},
    {'code': '5300', 'name': 'Bad Debt Expense', 'type': 'Operating Expenses', 'parent': '5000'},
]

JOURNAL_TYPES = [
    {'code': 'GJ', 'name': 'General Journal', 'prefix': 'GJ', 'description': 'General journal entries'},
    {'code': 'CR', 'name': 'Cash Receipt', 'prefix': 'CR', 'description': 'Cash receipts'},
    {'code': 'CP', 'name': 'Cash Payment', 'prefix': 'CP', 'description': 'Cash payments'},
    {'code': 'BR', 'name': 'Bank Receipt', 'prefix': 'BR', 'description': 'Bank receipts'},
    {'code': 'BP', 'name': 'Bank Payment', 'prefix': 'BP', 'description': 'Bank payments'},
    {'code': 'SJ', 'name': 'Sales Journal', 'prefix': 'SJ', 'description': 'Sales transactions'},
    {'code': 'PJ', 'name': 'Purchase Journal', 'prefix': 'PJ', 'description': 'Purchase transactions'},
    {'code': 'AJ', 'name': 'Adjustment Journal', 'prefix': 'AJ', 'description': 'Adjusting entries'},
    {'code': 'CN', 'name': 'Credit Note', 'prefix': 'CN', 'description': 'Credit notes / Sales returns'},
    {'code': 'DN', 'name': 'Debit Note', 'prefix': 'DN', 'description': 'Debit notes / Purchase returns'},
]

DEPARTMENTS = [
    'Administration', 'Finance', 'Human Resources', 'Information Technology',
    'Operations', 'Sales & Marketing', 'Accounts', 'Audit', 'Procurement', 'Logistics'
]

PROJECTS = [
    {'name': 'General Operations', 'description': 'General business operations'},
    {'name': 'Infrastructure Development', 'description': 'IT and infrastructure projects'},
    {'name': 'Marketing Campaign', 'description': 'Marketing and promotional activities'},
    {'name': 'Digital Transformation', 'description': 'Digital transformation initiatives'},
]

COST_CENTERS = [
    {'name': 'Head Office', 'description': 'Main corporate office'},
    {'name': 'Kathmandu Branch', 'description': 'Kathmandu branch office'},
    {'name': 'Pokhara Branch', 'description': 'Pokhara branch office'},
    {'name': 'Manufacturing Unit', 'description': 'Production facility'},
    {'name': 'Research & Development', 'description': 'R&D activities'},
]

TAX_CODES = [
    # VAT Codes
    {'name': 'VAT Standard Rate', 'rate': Decimal('13.00'), 'type': 'VAT', 'recoverable': True},
    {'name': 'VAT Zero Rate', 'rate': Decimal('0.00'), 'type': 'VAT', 'recoverable': True},
    {'name': 'VAT Exempt', 'rate': Decimal('0.00'), 'type': 'VAT', 'recoverable': False},
    # TDS Codes
    {'name': 'TDS Salary', 'rate': Decimal('1.00'), 'type': 'TDS', 'recoverable': False},
    {'name': 'TDS Professional Fee', 'rate': Decimal('5.00'), 'type': 'TDS', 'recoverable': False},
    {'name': 'TDS Contractor', 'rate': Decimal('2.00'), 'type': 'TDS', 'recoverable': False},
    {'name': 'TDS Rent', 'rate': Decimal('10.00'), 'type': 'TDS', 'recoverable': False},
    {'name': 'TDS Interest', 'rate': Decimal('15.00'), 'type': 'TDS', 'recoverable': False},
]

PAYMENT_TERMS = [
    {'code': 'NET30', 'name': 'Net 30 Days', 'days': 30, 'type': 'both'},
    {'code': 'NET15', 'name': 'Net 15 Days', 'days': 15, 'type': 'both'},
    {'code': 'NET45', 'name': 'Net 45 Days', 'days': 45, 'type': 'both'},
    {'code': 'NET60', 'name': 'Net 60 Days', 'days': 60, 'type': 'both'},
    {'code': 'COD', 'name': 'Cash on Delivery', 'days': 0, 'type': 'both'},
    {'code': '2/10NET30', 'name': '2% 10 Net 30', 'days': 30, 'discount': Decimal('2.00'), 'discount_days': 10, 'type': 'both'},
]

MODULES_AND_ENTITIES = {
    'accounting': {
        'name': 'Accounting',
        'description': 'Accounting and financial management',
        'entities': [
            ('fiscalyear', 'Fiscal Year'),
            ('accountingperiod', 'Accounting Period'),
            ('chartofaccount', 'Chart of Account'),
            ('journal', 'Journal Entry'),
            ('journaltype', 'Journal Type'),
            ('department', 'Department'),
            ('project', 'Project'),
            ('costcenter', 'Cost Center'),
            ('currency', 'Currency'),
            ('exchangerate', 'Exchange Rate'),
            ('taxauthority', 'Tax Authority'),
            ('taxtype', 'Tax Type'),
            ('taxcode', 'Tax Code'),
            ('vouchermodeconfig', 'Voucher Mode Config'),
            ('vendor', 'Vendor'),
            ('purchaseinvoice', 'Purchase Invoice'),
            ('customer', 'Customer'),
            ('salesinvoice', 'Sales Invoice'),
            ('paymentterm', 'Payment Term'),
            ('budget', 'Budget'),
            ('asset', 'Fixed Asset'),
        ]
    },
    'inventory': {
        'name': 'Inventory',
        'description': 'Inventory and warehouse management',
        'entities': [
            ('product', 'Product'),
            ('productcategory', 'Product Category'),
            ('warehouse', 'Warehouse'),
            ('location', 'Location'),
            ('batch', 'Batch'),
            ('inventoryitem', 'Inventory Item'),
            ('stockledger', 'Stock Ledger'),
            ('pricelist', 'Price List'),
        ]
    },
    'billing': {
        'name': 'Billing',
        'description': 'Subscription and billing management',
        'entities': [
            ('subscriptionplan', 'Subscription Plan'),
            ('subscription', 'Subscription'),
            ('invoice', 'Invoice'),
        ]
    },
    'usermanagement': {
        'name': 'User Management',
        'description': 'User and access management',
        'entities': [
            ('user', 'User'),
            ('role', 'Role'),
            ('permission', 'Permission'),
            ('organization', 'Organization'),
        ]
    },
    'service_management': {
        'name': 'Service Management',
        'description': 'Device and service lifecycle management',
        'entities': [
            ('device', 'Device'),
            ('devicecategory', 'Device Category'),
            ('servicecontract', 'Service Contract'),
        ]
    },
    'lpg_vertical': {
        'name': 'LPG Vertical',
        'description': 'LPG distribution management',
        'entities': [
            ('lpgproduct', 'LPG Product'),
            ('cylindertype', 'Cylinder Type'),
            ('dealer', 'Dealer'),
            ('inventorymovement', 'Inventory Movement'),
        ]
    },
}

ROLES = [
    {'code': 'ADMIN', 'name': 'Administrator', 'description': 'Full access to all features', 'is_system': True},
    {'code': 'MANAGER', 'name': 'Manager', 'description': 'Manager with approval and period closing rights', 'is_system': True},
    {'code': 'CLERK', 'name': 'Clerk', 'description': 'Clerk with create/edit access to transactions', 'is_system': True},
    {'code': 'AUDITOR', 'name': 'Auditor', 'description': 'Auditor with read-only access', 'is_system': True},
    {'code': 'USER', 'name': 'User', 'description': 'Basic user access', 'is_system': True},
]


# =============================================================================
# SEED FUNCTIONS
# =============================================================================

def get_or_create_superuser():
    """Create or get the default superuser."""
    username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
    email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
    password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin')
    
    if User.objects.filter(is_superuser=True).exists():
        user = User.objects.filter(is_superuser=True).first()
        logger.info(f"Using existing superuser: {user.username}")
        return user
    
    user = User.objects.create_superuser(username=username, email=email, password=password)
    logger.info(f"Created superuser: {username}")
    return user


def seed_tenancy(superuser):
    """Seed tenancy models: Tenant, SubscriptionPlan, TenantSubscription, TenantConfig."""
    from tenancy.models import Tenant, SubscriptionPlan, TenantSubscription, TenantConfig
    
    # Default tenant
    tenant, created = Tenant.objects.get_or_create(
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
    if created:
        logger.info("Created default tenant")
    
    # Subscription plans
    plans_data = [
        {'code': 'FREE', 'name': 'Free', 'price': 0, 'max_users': 3, 'max_storage': 1},
        {'code': 'STANDARD', 'name': 'Standard', 'price': 999, 'max_users': 10, 'max_storage': 10},
        {'code': 'PROFESSIONAL', 'name': 'Professional', 'price': 2999, 'max_users': 50, 'max_storage': 50},
        {'code': 'ENTERPRISE', 'name': 'Enterprise', 'price': 9999, 'max_users': 999, 'max_storage': 500},
    ]
    
    for plan_data in plans_data:
        plan, created = SubscriptionPlan.objects.get_or_create(
            code=plan_data['code'],
            defaults={
                'name': plan_data['name'],
                'description': f"{plan_data['name']} plan",
                'is_active': True,
                'base_price': plan_data['price'],
                'billing_cycle': 'monthly',
                'max_users': plan_data['max_users'],
                'max_storage_gb': plan_data['max_storage'],
                'features': {},
            }
        )
        if created:
            logger.info(f"Created subscription plan: {plan.name}")
    
    # Subscribe tenant to standard plan
    standard_plan = SubscriptionPlan.objects.get(code='STANDARD')
    today = date.today()
    sub, created = TenantSubscription.objects.get_or_create(
        tenant=tenant,
        plan=standard_plan,
        start_date=today,
        defaults={
            'end_date': today + timedelta(days=365),
            'auto_renew': True,
            'status': 'active',
            'billing_cycle': 'monthly',
            'price_per_period': 0,
            'currency_code': 'NPR',
            'discount_percentage': 0,
            'next_billing_date': today + timedelta(days=30),
        }
    )
    if created:
        logger.info("Created tenant subscription")
    
    # Sample config
    TenantConfig.objects.get_or_create(
        tenant=tenant,
        config_key='welcome_message',
        defaults={
            'config_value': 'Welcome to Himalytix ERP!',
            'data_type': 'string',
        }
    )
    
    return tenant


def seed_organization(superuser, tenant):
    """Create the default organization with address and contact."""
    from usermanagement.models import Organization, OrganizationAddress, OrganizationContact, UserOrganization
    
    org, created = Organization.objects.get_or_create(
        code='NEPAL-001',
        defaults={
            'name': 'Nepali Accounting System',
            'tenant': tenant,
            'type': 'company',
            'legal_name': 'Nepali Accounting System Pvt. Ltd.',
            'tax_id': 'NP-123456',
            'registration_number': 'REG-2024-001',
            'industry_code': 'ACCT',
            'fiscal_year_start_month': 4,  # Baisakh
            'fiscal_year_start_day': 1,
            'base_currency_code': 'NPR',
            'status': 'active',
            'is_active': True,
        }
    )
    if created:
        logger.info(f"Created organization: {org.name}")
    
    # Assign organization to superuser
    if superuser and not superuser.organization:
        superuser.organization = org
        superuser.save(update_fields=['organization'])
        logger.info(f"Assigned superuser to organization")
    
    # Address
    OrganizationAddress.objects.get_or_create(
        organization=org,
        address_type='head_office',
        defaults={
            'address_line1': '123 Main Street',
            'city': 'Kathmandu',
            'state_province': 'Bagmati',
            'postal_code': '44600',
            'country_code': 'NP',
            'is_primary': True,
        }
    )
    
    # Contact
    OrganizationContact.objects.get_or_create(
        organization=org,
        contact_type='admin',
        defaults={
            'name': 'Admin Contact',
            'email': 'admin@example.com',
            'phone': '+977-1-1234567',
            'job_title': 'Administrator',
            'is_primary': True,
        }
    )
    
    # UserOrganization mapping
    UserOrganization.objects.get_or_create(
        user=superuser,
        organization=org,
        defaults={
            'is_owner': True,
            'is_active': True,
            'role': 'owner',
        }
    )
    
    return org


def seed_currencies(superuser):
    """Seed currency data."""
    from accounting.models import Currency
    
    for curr in CURRENCIES:
        currency, created = Currency.objects.get_or_create(
            currency_code=curr['code'],
            defaults={
                'currency_name': curr['name'],
                'symbol': curr['symbol'],
                'is_active': True,
                'created_by': superuser,
            }
        )
        if created:
            logger.info(f"Created currency: {curr['code']}")


def seed_exchange_rates(org, superuser):
    """Seed exchange rates."""
    from accounting.models import Currency, CurrencyExchangeRate
    
    try:
        npr = Currency.objects.get(currency_code='NPR')
    except Currency.DoesNotExist:
        return
    
    today = date.today()
    for rate_data in EXCHANGE_RATES:
        try:
            to_curr = Currency.objects.get(currency_code=rate_data['to'])
            CurrencyExchangeRate.objects.get_or_create(
                organization=org,
                from_currency=npr,
                to_currency=to_curr,
                rate_date=today,
                defaults={
                    'exchange_rate': rate_data['rate'],
                    'source': 'seed',
                    'is_active': True,
                    'created_by': superuser,
                }
            )
        except Currency.DoesNotExist:
            continue
    
    logger.info("Seeded exchange rates")


def seed_account_types(superuser):
    """Seed account types."""
    from accounting.models import AccountType
    
    for at_data in ACCOUNT_TYPES:
        at, created = AccountType.objects.get_or_create(
            name=at_data['name'],
            nature=at_data['nature'],
            defaults={
                'classification': at_data['classification'],
                'balance_sheet_category': at_data.get('bs_category'),
                'income_statement_category': at_data.get('is_category'),
                'display_order': at_data['order'],
                'system_type': True,
                'created_by': superuser,
            }
        )
        if created:
            logger.info(f"Created account type: {at.name}")


def seed_chart_of_accounts(org, superuser):
    """Seed chart of accounts with proper hierarchy."""
    from accounting.models import AccountType, ChartOfAccount, Currency
    
    npr = Currency.objects.filter(currency_code='NPR').first()
    account_map = {}  # code -> account object
    
    # First pass: create all accounts without parents
    for acc_data in CHART_OF_ACCOUNTS:
        try:
            acc_type = AccountType.objects.get(name=acc_data['type'])
        except AccountType.DoesNotExist:
            logger.warning(f"Account type not found: {acc_data['type']}")
            continue
        
        acc, created = ChartOfAccount.objects.get_or_create(
            organization=org,
            account_code=acc_data['code'],
            defaults={
                'account_name': acc_data['name'],
                'account_type': acc_type,
                'description': f"Default {acc_data['name']} account",
                'is_active': True,
                'created_by': superuser,
                'currency': npr,
                'is_bank_account': acc_data.get('is_bank', False),
                'is_control_account': acc_data.get('is_control', False),
                'allow_manual_journal': True,
            }
        )
        account_map[acc_data['code']] = acc
        if created:
            logger.info(f"Created account: {acc.account_code} - {acc.account_name}")
    
    # Second pass: set parent relationships
    for acc_data in CHART_OF_ACCOUNTS:
        if acc_data.get('parent'):
            try:
                acc = ChartOfAccount.objects.get(organization=org, account_code=acc_data['code'])
                parent = account_map.get(acc_data['parent'])
                if parent and acc.parent_account != parent:
                    acc.parent_account = parent
                    acc.save(update_fields=['parent_account'])
            except ChartOfAccount.DoesNotExist:
                pass
    
    return account_map


def seed_fiscal_year_and_periods(org, superuser):
    """Seed fiscal year and accounting periods."""
    from accounting.models import FiscalYear, AccountingPeriod
    
    # Check for overlapping fiscal year
    fy = FiscalYear.objects.filter(
        organization=org,
        start_date__lte=FISCAL_YEAR_END,
        end_date__gte=FISCAL_YEAR_START
    ).first()
    
    if not fy:
        fy = FiscalYear.objects.create(
            organization=org,
            code='FY2082',
            name='Fiscal Year 2082-2083',
            start_date=FISCAL_YEAR_START,
            end_date=FISCAL_YEAR_END,
            status='open',
            is_current=True,
            is_default=True,
            created_by=superuser,
        )
        logger.info(f"Created fiscal year: {fy.name}")
        
        # Create periods
        for i, month in enumerate(NEPALI_MONTHS, 1):
            period, created = AccountingPeriod.objects.get_or_create(
                fiscal_year=fy,
                period_number=i,
                defaults={
                    'name': f"{month['nepali']} 2082-2083",
                    'start_date': month['start'],
                    'end_date': month['end'],
                    'status': 'open',
                    'is_current': i == 1,
                    'created_by': superuser,
                }
            )
            if created:
                logger.info(f"Created period: {period.name}")
    else:
        logger.info(f"Using existing fiscal year: {fy.name}")
    
    return fy


def seed_journal_types(org, superuser):
    """Seed journal types."""
    from accounting.models import JournalType
    
    for jt_data in JOURNAL_TYPES:
        jt, created = JournalType.objects.get_or_create(
            organization=org,
            code=jt_data['code'],
            defaults={
                'name': jt_data['name'],
                'description': jt_data['description'],
                'auto_numbering_prefix': jt_data['prefix'],
                'sequence_next': 1,
                'is_system_type': True,
                'is_active': True,
                'created_by': superuser,
            }
        )
        if created:
            logger.info(f"Created journal type: {jt.name}")


def seed_departments(org):
    """Seed departments."""
    from accounting.models import Department
    
    for dept_name in DEPARTMENTS:
        code = dept_name[:10].upper().replace(' ', '_').replace('&', '')
        dept, created = Department.objects.get_or_create(
            organization=org,
            code=code,
            defaults={'name': dept_name}
        )
        if created:
            logger.info(f"Created department: {dept.name}")


def seed_projects(org):
    """Seed projects."""
    from accounting.models import Project
    
    for proj_data in PROJECTS:
        proj, created = Project.objects.get_or_create(
            organization=org,
            name=proj_data['name'],
            defaults={
                'description': proj_data['description'],
                'is_active': True,
                'start_date': date.today(),
            }
        )
        if created:
            logger.info(f"Created project: {proj.name}")


def seed_cost_centers(org):
    """Seed cost centers."""
    from accounting.models import CostCenter
    
    for cc_data in COST_CENTERS:
        code = cc_data['name'][:10].upper().replace(' ', '_')
        cc, created = CostCenter.objects.get_or_create(
            organization=org,
            code=code,
            defaults={
                'name': cc_data['name'],
                'description': cc_data['description'],
                'is_active': True,
            }
        )
        if created:
            logger.info(f"Created cost center: {cc.name}")


def seed_tax_data(org, superuser):
    """Seed tax authority, types, and codes."""
    from accounting.models import TaxAuthority, TaxType, TaxCode
    
    # Tax Authority
    authority, created = TaxAuthority.objects.get_or_create(
        organization=org,
        name='Inland Revenue Department',
        defaults={
            'country_code': 'NP',
            'description': 'Nepal Tax Authority - Inland Revenue Department',
            'is_active': True,
            'is_default': True,
            'created_by': superuser,
        }
    )
    if created:
        logger.info("Created tax authority: IRD")
    
    # Tax Types
    tax_types = {}
    for tt_name in ['Value Added Tax (VAT)', 'Tax Deducted at Source (TDS)', 'Income Tax']:
        freq = 'annual' if 'Income' in tt_name else 'monthly'
        tt, created = TaxType.objects.get_or_create(
            organization=org,
            name=tt_name,
            defaults={
                'authority': authority,
                'description': f"Nepal {tt_name}",
                'filing_frequency': freq,
                'is_active': True,
                'created_by': superuser,
            }
        )
        key = 'VAT' if 'VAT' in tt_name else ('TDS' if 'TDS' in tt_name else 'IT')
        tax_types[key] = tt
        if created:
            logger.info(f"Created tax type: {tt.name}")
    
    # Tax Codes
    for tc_data in TAX_CODES:
        tt = tax_types.get(tc_data['type'], tax_types.get('VAT'))
        tc, created = TaxCode.objects.get_or_create(
            organization=org,
            name=tc_data['name'],
            defaults={
                'tax_type': tt,
                'tax_authority': authority,
                'tax_rate': tc_data['rate'],
                'rate': tc_data['rate'],
                'description': f"Nepal {tc_data['name']}",
                'is_active': True,
                'is_recoverable': tc_data['recoverable'],
                'effective_from': FISCAL_YEAR_START,
                'created_by': superuser,
            }
        )
        if created:
            logger.info(f"Created tax code: {tc.name}")


def seed_payment_terms(org, superuser):
    """Seed payment terms."""
    from accounting.models import PaymentTerm
    
    for pt_data in PAYMENT_TERMS:
        pt, created = PaymentTerm.objects.get_or_create(
            organization=org,
            code=pt_data['code'],
            defaults={
                'name': pt_data['name'],
                'term_type': pt_data['type'],
                'net_due_days': pt_data['days'],
                'discount_percent': pt_data.get('discount', Decimal('0')),
                'discount_days': pt_data.get('discount_days'),
                'is_active': True,
                'created_by': superuser,
            }
        )
        if created:
            logger.info(f"Created payment term: {pt.name}")


def seed_voucher_mode_config(org, superuser, journal_type):
    """Seed default voucher mode config."""
    from accounting.models import VoucherModeConfig
    
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
    
    vmc, created = VoucherModeConfig.objects.get_or_create(
        organization=org,
        code='STANDARD',
        defaults={
            'name': 'Standard Voucher',
            'description': 'Standard voucher configuration for Nepal',
            'is_default': True,
            'is_active': True,
            'journal_type': journal_type,
            'layout_style': 'standard',
            'show_account_balances': True,
            'show_tax_details': True,
            'show_dimensions': True,
            'allow_multiple_currencies': True,
            'require_line_description': True,
            'default_currency': 'NPR',
            'ui_schema': default_ui_schema,
            'created_by': superuser,
        }
    )
    if created:
        logger.info("Created voucher mode config: Standard Voucher")


def seed_modules_and_permissions():
    """Seed modules, entities, and permissions."""
    from usermanagement.models import Module, Entity, Permission
    
    for module_code, module_data in MODULES_AND_ENTITIES.items():
        module, created = Module.objects.get_or_create(
            code=module_code,
            defaults={
                'name': module_data['name'],
                'description': module_data['description'],
                'is_active': True,
            }
        )
        if created:
            logger.info(f"Created module: {module.name}")
        
        for entity_code, entity_name in module_data['entities']:
            entity, created = Entity.objects.get_or_create(
                module=module,
                code=entity_code,
                defaults={
                    'name': entity_name,
                    'description': f'{entity_name} management',
                    'is_active': True,
                }
            )
            if created:
                logger.info(f"Created entity: {entity.name}")
            
            # Standard CRUD permissions
            actions = ['view', 'add', 'change', 'delete']
            
            # Special permissions for journal
            if entity_code == 'journal':
                actions.extend(['submit_journal', 'approve_journal', 'reject_journal', 'post_journal', 'reverse_journal'])
            elif entity_code == 'accountingperiod':
                actions.extend(['close_period', 'reopen_period'])
            elif entity_code == 'fiscalyear':
                actions.extend(['close_fiscalyear', 'reopen_fiscalyear'])
            
            for action in actions:
                perm, created = Permission.objects.get_or_create(
                    module=module,
                    entity=entity,
                    action=action,
                    defaults={
                        'name': f'Can {action.replace("_", " ")} {entity_name}',
                        'codename': f'{module_code}_{entity_code}_{action}',
                        'description': f'Can {action.replace("_", " ")} {entity_name}',
                        'is_active': True,
                    }
                )


def seed_roles(org, superuser):
    """Seed roles and assign permissions."""
    from usermanagement.models import Role, Permission, UserRole
    
    all_permissions = list(Permission.objects.filter(is_active=True))
    view_permissions = [p for p in all_permissions if p.action == 'view']
    
    for role_data in ROLES:
        role, created = Role.objects.get_or_create(
            organization=org,
            code=role_data['code'],
            defaults={
                'name': role_data['name'],
                'description': role_data['description'],
                'is_system': role_data['is_system'],
                'is_active': True,
                'created_by': superuser,
                'updated_by': superuser,
            }
        )
        
        # Assign permissions based on role
        if role_data['code'] == 'ADMIN':
            role.permissions.set(all_permissions)
        elif role_data['code'] == 'AUDITOR':
            role.permissions.set(view_permissions)
        elif role_data['code'] == 'USER':
            role.permissions.set(view_permissions)
        elif role_data['code'] == 'CLERK':
            # View + journal CRUD + submit
            clerk_perms = [p for p in all_permissions if p.action in ['view', 'add', 'change', 'delete', 'submit_journal']]
            role.permissions.set(clerk_perms)
        elif role_data['code'] == 'MANAGER':
            # View + journal CRUD + approve/post/close
            manager_actions = ['view', 'add', 'change', 'delete', 'submit_journal', 'approve_journal', 
                             'reject_journal', 'post_journal', 'close_period', 'reopen_period']
            manager_perms = [p for p in all_permissions if p.action in manager_actions]
            role.permissions.set(manager_perms)
        
        if created:
            logger.info(f"Created role: {role.name}")
    
    # Assign admin role to superuser
    admin_role = Role.objects.get(organization=org, code='ADMIN')
    UserRole.objects.get_or_create(
        user=superuser,
        role=admin_role,
        organization=org,
        defaults={
            'is_active': True,
            'created_by': superuser,
            'updated_by': superuser,
        }
    )


def seed_default_vendor(org, superuser, account_map):
    """Seed Nepal Oil Corporation vendor."""
    from accounting.models import Vendor, Currency
    
    npr = Currency.objects.filter(currency_code='NPR').first()
    ap_account = account_map.get('2010')  # Accounts Payable
    
    if not ap_account:
        ap_account = account_map.get('2000')  # Fallback to Liabilities
    
    if ap_account:
        vendor, created = Vendor.objects.get_or_create(
            organization=org,
            code='NOC',
            defaults={
                'display_name': 'Nepal Oil Corporation',
                'legal_name': 'Nepal Oil Corporation',
                'tax_id': '',
                'default_currency': npr,
                'accounts_payable_account': ap_account,
                'status': 'active',
                'created_by': superuser,
            }
        )
        if created:
            logger.info("Created vendor: Nepal Oil Corporation")


def seed_inventory_data(org, superuser):
    """Seed inventory base data (warehouse, categories)."""
    try:
        from Inventory.models import Warehouse, ProductCategory
        
        # Default warehouse
        wh, created = Warehouse.objects.get_or_create(
            organization=org,
            code='MAIN',
            defaults={
                'name': 'Main Warehouse',
                'address_line1': 'Kathmandu',
                'city': 'Kathmandu',
                'country_code': 'NP',
                'is_active': True,
            }
        )
        if created:
            logger.info("Created warehouse: Main Warehouse")
        
        # Product categories
        categories = ['General', 'Raw Materials', 'Finished Goods', 'Services', 'Consumables']
        for cat_name in categories:
            code = cat_name[:10].upper().replace(' ', '_')
            cat, created = ProductCategory.objects.get_or_create(
                organization=org,
                code=code,
                defaults={
                    'name': cat_name,
                    'is_active': True,
                }
            )
            if created:
                logger.info(f"Created product category: {cat.name}")
                
    except ImportError:
        logger.warning("Inventory module not available, skipping inventory seed")


def seed_lpg_data(org):
    """Seed LPG vertical data."""
    try:
        from lpg_vertical.models import CylinderType, LpgProduct
        
        # Cylinder types
        cylinder_types = [
            {'name': '14.2 kg', 'kg': Decimal('14.2')},
            {'name': '5 kg', 'kg': Decimal('5.0')},
            {'name': '2 kg', 'kg': Decimal('2.0')},
            {'name': '19 kg Commercial', 'kg': Decimal('19.0')},
            {'name': '33.3 kg Commercial', 'kg': Decimal('33.3')},
        ]
        
        for ct_data in cylinder_types:
            ct, created = CylinderType.objects.get_or_create(
                organization=org,
                name=ct_data['name'],
                defaults={
                    'kg_per_cylinder': ct_data['kg'],
                    'is_active': True,
                }
            )
            if created:
                logger.info(f"Created cylinder type: {ct.name}")
        
        # LPG Products
        products = [
            {'code': 'LPG-BULK', 'name': 'LPG Bulk', 'is_bulk': True},
            {'code': 'LPG-CYLINDER', 'name': 'LPG Cylinder Gas', 'is_bulk': False},
        ]
        
        for prod_data in products:
            prod, created = LpgProduct.objects.get_or_create(
                organization=org,
                code=prod_data['code'],
                defaults={
                    'name': prod_data['name'],
                    'is_bulk': prod_data['is_bulk'],
                    'is_active': True,
                }
            )
            if created:
                logger.info(f"Created LPG product: {prod.name}")
                
    except ImportError:
        logger.warning("LPG vertical module not available, skipping LPG seed")


def seed_service_management_data(org):
    """Seed service management data."""
    try:
        from service_management.models import DeviceCategory, DeviceModel
        
        # Device categories
        categories = [
            {'code': 'ROUTER', 'name': 'Network Router'},
            {'code': 'SWITCH', 'name': 'Network Switch'},
            {'code': 'SERVER', 'name': 'Server'},
            {'code': 'IOT', 'name': 'IoT Device'},
            {'code': 'PRINTER', 'name': 'Printer'},
        ]
        
        for cat_data in categories:
            cat, created = DeviceCategory.objects.get_or_create(
                organization=org,
                code=cat_data['code'],
                defaults={
                    'name': cat_data['name'],
                    'is_active': True,
                }
            )
            if created:
                logger.info(f"Created device category: {cat.name}")
                
    except ImportError:
        logger.warning("Service management module not available, skipping service seed")


def seed_demo_journal(org, superuser, fy, account_map):
    """Create a demo journal entry."""
    from accounting.models import Journal, JournalLine, JournalType, AccountingPeriod
    
    # Only create if no journals exist
    if Journal.objects.filter(organization=org).exists():
        return
    
    period = AccountingPeriod.objects.filter(fiscal_year=fy).first()
    journal_type = JournalType.objects.filter(organization=org, code='GJ').first()
    cash_account = account_map.get('1010')
    expense_account = account_map.get('5130')  # Office Supplies
    
    if not all([period, journal_type, cash_account, expense_account]):
        logger.warning("Cannot create demo journal - missing required data")
        return
    
    demo_journal = Journal.objects.create(
        organization=org,
        journal_number='GJ0001',
        journal_type=journal_type,
        period=period,
        journal_date=period.start_date,
        description='Demo voucher entry - Office Supplies Purchase',
        currency_code='NPR',
        exchange_rate=1,
        status='draft',
        created_by=superuser,
    )
    
    JournalLine.objects.create(
        journal=demo_journal,
        line_number=1,
        account=expense_account,
        debit_amount=Decimal('5000.00'),
        credit_amount=Decimal('0.00'),
        description='Office supplies purchase',
        fx_rate=Decimal('1.00'),
        amount_txn=Decimal('5000.00'),
        amount_base=Decimal('5000.00'),
        functional_debit_amount=Decimal('5000.00'),
        functional_credit_amount=Decimal('0.00'),
        created_by=superuser,
    )
    
    JournalLine.objects.create(
        journal=demo_journal,
        line_number=2,
        account=cash_account,
        debit_amount=Decimal('0.00'),
        credit_amount=Decimal('5000.00'),
        description='Cash payment for office supplies',
        fx_rate=Decimal('1.00'),
        amount_txn=Decimal('5000.00'),
        amount_base=Decimal('5000.00'),
        functional_debit_amount=Decimal('0.00'),
        functional_credit_amount=Decimal('5000.00'),
        created_by=superuser,
    )
    
    logger.info("Created demo journal entry")


# =============================================================================
# MAIN SEED FUNCTION
# =============================================================================

@transaction.atomic
def seed_all():
    """
    Main function to seed all data for a fresh database.
    This is idempotent - safe to run multiple times.
    """
    logger.info("=" * 60)
    logger.info("STARTING COMPREHENSIVE DATABASE SEED")
    logger.info("=" * 60)
    
    # 1. Create superuser
    superuser = get_or_create_superuser()
    
    # 2. Seed tenancy
    tenant = seed_tenancy(superuser)
    
    # 3. Seed organization
    org = seed_organization(superuser, tenant)
    
    # 4. Seed currencies
    seed_currencies(superuser)
    
    # 5. Seed exchange rates
    seed_exchange_rates(org, superuser)
    
    # 6. Seed account types
    seed_account_types(superuser)
    
    # 7. Seed chart of accounts
    account_map = seed_chart_of_accounts(org, superuser)
    
    # 8. Seed fiscal year and periods
    fy = seed_fiscal_year_and_periods(org, superuser)
    
    # 9. Seed journal types
    seed_journal_types(org, superuser)
    
    # 10. Seed dimensions
    seed_departments(org)
    seed_projects(org)
    seed_cost_centers(org)
    
    # 11. Seed tax data
    seed_tax_data(org, superuser)
    
    # 12. Seed payment terms
    seed_payment_terms(org, superuser)
    
    # 13. Seed voucher mode config
    from accounting.models import JournalType
    gj = JournalType.objects.filter(organization=org, code='GJ').first()
    if gj:
        seed_voucher_mode_config(org, superuser, gj)
    
    # 14. Seed modules, entities, and permissions
    seed_modules_and_permissions()
    
    # 15. Seed roles
    seed_roles(org, superuser)
    
    # 16. Seed vendor (NOC)
    seed_default_vendor(org, superuser, account_map)
    
    # 17. Seed inventory data
    seed_inventory_data(org, superuser)
    
    # 18. Seed LPG data
    seed_lpg_data(org)
    
    # 19. Seed service management data
    seed_service_management_data(org)
    
    # 20. Create demo journal
    seed_demo_journal(org, superuser, fy, account_map)
    
    logger.info("=" * 60)
    logger.info("DATABASE SEED COMPLETED SUCCESSFULLY!")
    logger.info("=" * 60)
    logger.info(f"""
Summary:
- Organization: {org.name} ({org.code})
- Fiscal Year: {fy.name}
- Base Currency: NPR (Nepalese Rupee)
- Superuser: {superuser.username}
- Tax Authority: Inland Revenue Department
- Default Vendor: Nepal Oil Corporation (NOC)
""")


if __name__ == '__main__':
    seed_all()
