from __future__ import annotations

from typing import Optional

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.utils import IntegrityError

from accounting.models import (
    AccountType,
    ChartOfAccount,
    Currency,
    ExpenseCategory,
    JournalType,
)
from usermanagement.models import Organization


DEFAULT_CATEGORIES = [
    {'code': 'OFFICE', 'name': 'Office Supplies'},
    {'code': 'RENT', 'name': 'Rent'},
    {'code': 'TRAVEL', 'name': 'Travel & Meals'},
]


class Command(BaseCommand):
    help = 'Seed each organization with an expense journal type and common expense categories.'

    def handle(self, *args, **options):
        organizations = Organization.objects.filter(is_active=True)
        if not organizations.exists():
            self.stdout.write('No active organizations found. Nothing to seed.')
            return

        for organization in organizations:
            try:
                with transaction.atomic():
                    expense_type = self._get_or_create_account_type('expense', 'ATEXP', 'Expense')
                    asset_type = self._get_or_create_account_type('asset', 'ATAST', 'Asset')
                    expense_account = self._get_or_create_account(
                        organization,
                        expense_type,
                        suggested_code='5100',
                        name='Default Expense Account',
                    )
                    payment_account = self._get_or_create_account(
                        organization,
                        asset_type,
                        suggested_code='1100',
                        name='Default Cash Account',
                        is_bank=True,
                    )
                    journal_type = self._ensure_journal_type(organization)
                    self._ensure_expense_categories(
                        organization,
                        expense_account,
                        payment_account,
                    )
                    self.stdout.write(
                        f"Seeded default expense resources for {organization.code} (JournalType={journal_type.code})."
                    )
            except IntegrityError as exc:
                self.stderr.write(f"Skipping {organization.code}: {exc}")

    def _get_or_create_account_type(self, nature: str, code_prefix: str, friendly: str) -> AccountType:
        defaults = {
            'nature': nature,
            'name': f"Default {friendly} Account Type",
            'classification': 'Default',
            'display_order': 999,
            'system_type': False,
        }
        account_type, _ = AccountType.objects.get_or_create(
            code=f"{code_prefix}-DEFAULT",
            defaults=defaults,
        )
        return account_type

    def _get_currency_for_org(self, organization: Organization):
        if organization.base_currency_code:
            return organization.base_currency_code
        if organization.base_currency_code_id:
            candidate = Currency.objects.filter(currency_code=organization.base_currency_code_id).first()
            if candidate:
                return candidate
        default_code = getattr(settings, 'DEFAULT_CURRENCY', 'USD')
        return Currency.objects.filter(currency_code=default_code).first()

    def _get_or_create_account(
        self,
        organization: Organization,
        account_type: AccountType,
        *,
        suggested_code: str,
        name: str,
        is_bank: bool = False,
    ) -> ChartOfAccount:
        currency = self._get_currency_for_org(organization)
        if not currency:
            currency = Currency.objects.first()
        defaults = {
            'account_type': account_type,
            'account_name': name,
            'currency': currency,
            'use_custom_code': True,
            'custom_code': suggested_code,
            'is_bank_account': is_bank,
        }
        account, created = ChartOfAccount.objects.get_or_create(
            organization=organization,
            account_code=suggested_code,
            defaults=defaults,
        )
        if created and not account.currency:
            account.currency = currency
            account.save()
        return account

    def _ensure_journal_type(self, organization: Organization) -> JournalType:
        defaults = {
            'name': 'Expense Journal',
            'auto_numbering_prefix': 'EXP',
            'requires_approval': False,
            'is_active': True,
        }
        journal_type, _ = JournalType.objects.get_or_create(organization=organization, code='EXPENSE', defaults=defaults)
        return journal_type

    def _ensure_expense_categories(
        self,
        organization: Organization,
        expense_account: ChartOfAccount,
        payment_account: ChartOfAccount,
    ) -> None:
        for category in DEFAULT_CATEGORIES:
            ExpenseCategory.objects.get_or_create(
                organization=organization,
                code=category['code'],
                defaults={
                    'name': category['name'],
                    'expense_account': expense_account,
                    'default_payment_account': payment_account,
                },
            )
*** End of File