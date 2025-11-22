"""Test data factories for accounting test suite.

These helpers centralize the creation of organizations, periods, tax
structures, and other frequently used models so that individual tests
remain focused on behaviour instead of schema boilerplate.
"""
from __future__ import annotations

import itertools
from datetime import date, timedelta
from typing import Optional

from django.contrib.auth import get_user_model
from django.utils import timezone

from accounting.models import (
    AccountType,
    AccountingPeriod,
    ChartOfAccount,
    Currency,
    FiscalYear,
    Journal,
    JournalType,
    TaxAuthority,
    TaxCode,
    TaxType,
    VoucherModeConfig,
)
from usermanagement.models import Organization, UserOrganization

__all__ = [
    "create_account_type",
    "create_accounting_period",
    "create_chart_of_account",
    "create_currency",
    "create_fiscal_year",
    "create_journal",
    "create_journal_type",
    "create_organization",
    "create_tax_authority",
    "create_tax_code",
    "create_tax_type",
    "create_voucher_mode_config",
    "create_user",
]


_sequence = itertools.count(1)


def _unique_suffix() -> int:
    return next(_sequence)


def create_organization(**overrides) -> Organization:
    """Create an organization with sane defaults for tests."""
    idx = _unique_suffix()
    defaults = {
        "name": overrides.get("name") or f"Test Org {idx}",
        "code": overrides.get("code") or f"ORG{idx:03d}",
        "type": overrides.get("type") or "company",
        "status": overrides.get("status") or "active",
        "is_active": overrides.get("is_active", True),
        "base_currency_code": overrides.get("base_currency_code", "USD"),
    }
    defaults.update(overrides)
    return Organization.objects.create(**defaults)


def create_currency(code: str = "USD", name: str = "US Dollar", symbol: str = "$", **overrides) -> Currency:
    """Return the requested currency, creating it if necessary."""
    defaults = {
        "currency_name": name,
        "symbol": symbol,
    }
    defaults.update(overrides)
    obj, _ = Currency.objects.get_or_create(currency_code=code, defaults=defaults)
    return obj


def create_account_type(**overrides) -> AccountType:
    idx = _unique_suffix()
    nature = overrides.get("nature", "asset")
    defaults = {
        "code": overrides.get("code") or f"AT{idx:03d}",
        "name": overrides.get("name") or f"Auto {nature.title()} {idx}",
        "nature": nature,
        "classification": overrides.get("classification") or "Statement",
        "display_order": overrides.get("display_order", idx),
        "root_code_prefix": overrides.get("root_code_prefix"),
        "root_code_step": overrides.get("root_code_step", 100),
    }
    defaults.update(overrides)
    return AccountType.objects.create(**defaults)


def create_fiscal_year(organization: Optional[Organization] = None, **overrides) -> FiscalYear:
    organization = organization or create_organization()
    today = timezone.now().date()
    start = overrides.get("start_date") or date(today.year, 1, 1)
    end = overrides.get("end_date") or date(today.year, 12, 31)
    defaults = {
        "organization": organization,
        "code": overrides.get("code") or f"FY{today.year % 100:02d}",
        "name": overrides.get("name") or f"Fiscal {today.year}",
        "start_date": start,
        "end_date": end,
        "is_current": overrides.get("is_current", True),
    }
    defaults.update(overrides)
    return FiscalYear.objects.create(**defaults)


def create_accounting_period(
    organization: Optional[Organization] = None,
    fiscal_year: Optional[FiscalYear] = None,
    **overrides,
) -> AccountingPeriod:
    fiscal_year = fiscal_year or create_fiscal_year(organization=organization)
    organization = fiscal_year.organization
    start = overrides.get("start_date") or fiscal_year.start_date
    end = overrides.get("end_date") or min(fiscal_year.end_date, start + timedelta(days=29))
    defaults = {
        "fiscal_year": fiscal_year,
        "organization": organization,
        "period_number": overrides.get("period_number", 1),
        "name": overrides.get("name") or f"{fiscal_year.code}-P1",
        "start_date": start,
        "end_date": end,
        "status": overrides.get("status", "open"),
        "is_current": overrides.get("is_current", True),
    }
    defaults.update(overrides)
    return AccountingPeriod.objects.create(**defaults)


def create_journal_type(organization: Optional[Organization] = None, **overrides) -> JournalType:
    organization = organization or create_organization()
    idx = _unique_suffix()
    defaults = {
        "organization": organization,
        "code": overrides.get("code") or f"JT{idx:02d}",
        "name": overrides.get("name") or f"Journal Type {idx}",
        "auto_numbering_prefix": overrides.get("auto_numbering_prefix", "GJ"),
    }
    defaults.update(overrides)
    return JournalType.objects.create(**defaults)


def create_chart_of_account(
    organization: Optional[Organization] = None,
    account_type: Optional[AccountType] = None,
    currency: Optional[Currency] = None,
    **overrides,
) -> ChartOfAccount:
    organization = organization or create_organization()
    account_type = account_type or create_account_type()
    currency = currency or create_currency()
    idx = _unique_suffix()
    defaults = {
        "organization": organization,
        "account_type": account_type,
        "currency": currency,
        "account_code": overrides.get("account_code") or f"{1000 + idx:04d}",
        "account_name": overrides.get("account_name") or f"Account {idx}",
    }
    defaults.update(overrides)
    return ChartOfAccount.objects.create(**defaults)


def create_tax_authority(organization: Optional[Organization] = None, **overrides) -> TaxAuthority:
    organization = organization or create_organization()
    idx = _unique_suffix()
    defaults = {
        "organization": organization,
        "code": overrides.get("code") or f"TA{idx:03d}",
        "name": overrides.get("name") or f"Tax Authority {idx}",
    }
    defaults.update(overrides)
    return TaxAuthority.objects.create(**defaults)


def create_tax_type(
    organization: Optional[Organization] = None,
    authority: Optional[TaxAuthority] = None,
    **overrides,
) -> TaxType:
    organization = organization or authority.organization if authority else create_organization()
    authority = authority or create_tax_authority(organization=organization)
    idx = _unique_suffix()
    defaults = {
        "organization": organization,
        "authority": authority,
        "code": overrides.get("code") or f"TT{idx:03d}",
        "name": overrides.get("name") or f"Tax Type {idx}",
    }
    defaults.update(overrides)
    return TaxType.objects.create(**defaults)


def create_tax_code(
    organization: Optional[Organization] = None,
    tax_type: Optional[TaxType] = None,
    authority: Optional[TaxAuthority] = None,
    **overrides,
) -> TaxCode:
    tax_type = tax_type or create_tax_type(organization=organization, authority=authority)
    organization = tax_type.organization
    authority = authority or tax_type.authority
    idx = _unique_suffix()
    defaults = {
        "organization": organization,
        "tax_type": tax_type,
        "tax_authority": authority,
        "code": overrides.get("code") or f"TC{idx:03d}",
        "name": overrides.get("name") or f"Tax Code {idx}",
    }
    defaults.update(overrides)
    return TaxCode.objects.create(**defaults)


def create_user(
    *,
    organization: Optional[Organization] = None,
    username: Optional[str] = None,
    password: str = "Passw0rd!",
    **overrides,
):
    """Create a CustomUser and ensure organization membership."""
    organization = organization or create_organization()
    idx = _unique_suffix()
    username = username or f"user{idx}"
    email = overrides.get("email") or f"{username}@example.com"
    defaults = {
        "organization": organization,
        "email": email,
        "full_name": overrides.get("full_name") or f"Test User {idx}",
        "role": overrides.get("role") or "user",
        "status": overrides.get("status", "active"),
    }
    defaults.update(overrides)
    user = get_user_model().objects.create_user(
        username=username,
        password=password,
        **defaults,
    )
    UserOrganization.objects.get_or_create(
        user=user,
        organization=organization,
        defaults={"is_active": True, "role": defaults.get("role", "member")},
    )
    return user


def create_voucher_mode_config(
    *,
    organization: Optional[Organization] = None,
    journal_type: Optional[JournalType] = None,
    **overrides,
) -> VoucherModeConfig:
    organization = organization or create_organization()
    journal_type = journal_type or create_journal_type(organization=organization)
    idx = _unique_suffix()
    defaults = {
        "organization": organization,
        "journal_type": journal_type,
        "code": overrides.pop("code", f"VC{idx:03d}"),
        "name": overrides.pop("name", f"Voucher Config {idx}"),
        "is_default": overrides.pop("is_default", False),
        "show_tax_details": overrides.pop("show_tax_details", True),
        "show_dimensions": overrides.pop("show_dimensions", True),
        "allow_multiple_currencies": overrides.pop("allow_multiple_currencies", False),
        "require_line_description": overrides.pop("require_line_description", True),
        "default_currency": overrides.pop("default_currency", organization.base_currency_code or "USD"),
    }
    defaults.update(overrides)
    return VoucherModeConfig.objects.create(**defaults)


def create_journal(
    *,
    organization: Optional[Organization] = None,
    journal_type: Optional[JournalType] = None,
    period: Optional[AccountingPeriod] = None,
    fiscal_year: Optional[FiscalYear] = None,
    journal_date: Optional[date] = None,
    created_by=None,
    **overrides,
) -> Journal:
    organization = organization or create_organization()
    journal_type = journal_type or create_journal_type(organization=organization)
    fiscal_year = fiscal_year or period.fiscal_year if period else create_fiscal_year(organization=organization)
    period = period or create_accounting_period(fiscal_year=fiscal_year)
    user = created_by or overrides.pop("created_by", None) or create_user(organization=organization)
    journal_date = journal_date or timezone.now().date()
    idx = _unique_suffix()
    defaults = {
        "organization": organization,
        "journal_type": journal_type,
        "period": period,
        "journal_date": journal_date,
        "journal_number": overrides.pop("journal_number", f"{journal_type.code or 'JNL'}-{idx:03d}"),
        "currency_code": overrides.pop("currency_code", organization.base_currency_code or "USD"),
        "status": overrides.pop("status", "draft"),
        "created_by": user,
    }
    defaults.update(overrides)
    return Journal.objects.create(**defaults)
