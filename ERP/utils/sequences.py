"""
Sequence & Code Generation Utilities

Provides centralized sequence generation for voucher numbers, account codes,
and other auto-generated identifiers. Ensures uniqueness and proper formatting.
"""

import string
from typing import Optional, Any, Dict, Union
from datetime import datetime, date
from django.db import models, transaction
from django.db.models import Max, Q
from django.utils import timezone

from .organization import OrganizationService
from usermanagement.models import Organization


class SequenceGenerator:
    """
    Centralized service for generating sequential identifiers.

    Handles voucher numbers, document numbers, and other sequential codes
    with proper organization isolation and uniqueness guarantees.
    """

    @staticmethod
    def generate_voucher_number(
        voucher_type: str,
        organization: Organization,
        date_obj: Optional[date] = None,
        fiscal_year: Optional[Any] = None
    ) -> str:
        """
        Generate a unique voucher number for the given type and organization.

        Args:
            voucher_type: Type of voucher (e.g., 'journal', 'invoice', 'payment')
            organization: Organization instance
            date_obj: Date for the voucher (defaults to today)
            fiscal_year: Fiscal year instance (optional)

        Returns:
            Formatted voucher number string

        Usage:
            # In model save method
            if not self.voucher_number:
                self.voucher_number = SequenceGenerator.generate_voucher_number(
                    'journal', self.organization, self.journal_date
                )
        """
        if not organization:
            raise ValueError("Organization is required for voucher number generation")

        date_obj = date_obj or timezone.localdate()

        # Get or create sequence configuration
        config = VoucherSequenceConfig.get_or_create_config(
            organization, voucher_type
        )

        # Generate the number
        return config.generate_number(date_obj, fiscal_year)

    @staticmethod
    def generate_account_code(
        account_type: Any,
        parent_account: Optional[Any] = None,
        organization: Optional[Organization] = None
    ) -> str:
        """
        Generate a unique account code for COA.

        Args:
            account_type: AccountType instance
            parent_account: Parent account (optional)
            organization: Organization instance

        Returns:
            Formatted account code

        Usage:
            # In ChartOfAccount model
            if not self.account_code:
                self.account_code = SequenceGenerator.generate_account_code(
                    self.account_type, self.parent_account, self.organization
                )
        """
        if not account_type:
            raise ValueError("Account type is required for code generation")

        # Get root code and step from account type
        root_code = account_type.root_code_prefix or account_type.get_default_root_code_prefix(account_type.nature)
        step = account_type.root_code_step or 100

        if parent_account:
            # Generate child code
            return SequenceGenerator._generate_child_code(parent_account, organization)
        else:
            # Generate root level code
            return SequenceGenerator._generate_root_code(root_code, step, organization)

    @staticmethod
    def _generate_child_code(parent_account: Any, organization: Organization) -> str:
        """
        Generate child account code under a parent.
        """
        if not parent_account or not parent_account.account_code:
            raise ValueError("Parent account with code is required")

        # Get existing siblings
        siblings = parent_account.get_children()
        if organization:
            siblings = OrganizationService.filter_queryset_by_org(siblings, organization)

        # Find the highest suffix
        max_suffix = 0
        base_code = parent_account.account_code

        for sibling in siblings:
            if sibling.account_code.startswith(base_code + "."):
                try:
                    suffix = int(sibling.account_code.replace(base_code + ".", ""))
                    max_suffix = max(max_suffix, suffix)
                except ValueError:
                    continue

        next_suffix = max_suffix + 1
        return "02d"

    @staticmethod
    def _generate_root_code(root_prefix: str, step: int, organization: Organization) -> str:
        """
        Generate root level account code.
        """
        # Get the model (assuming ChartOfAccount is available)
        from accounting.models import ChartOfAccount

        # Find existing codes with this prefix
        existing_codes = ChartOfAccount.objects.filter(
            account_code__startswith=root_prefix,
            parent_account__isnull=True
        )

        if organization:
            existing_codes = OrganizationService.filter_queryset_by_org(
                existing_codes, organization
            )

        max_code = 0
        for account in existing_codes:
            try:
                code_num = int(account.account_code)
                if str(code_num).startswith(root_prefix):
                    max_code = max(max_code, code_num)
            except ValueError:
                continue

        if max_code >= int(root_prefix):
            next_code = max_code + step
        else:
            next_code = int(root_prefix)

        # Ensure uniqueness
        while ChartOfAccount.objects.filter(
            account_code=str(next_code),
            organization=organization
        ).exists():
            next_code += step

        return str(next_code).zfill(len(root_prefix))

    @staticmethod
    def generate_entity_code(
        model: models.Model,
        prefix: str = '',
        organization: Optional[Organization] = None,
        date_obj: Optional[date] = None,
        suffix: str = '',
        padding: int = 4
    ) -> str:
        """
        Generic entity code generator.

        Args:
            model: Django model class
            prefix: Code prefix
            organization: Organization instance
            date_obj: Date for the code
            suffix: Code suffix
            padding: Number padding length

        Returns:
            Generated code string

        Usage:
            # Generate customer code
            code = SequenceGenerator.generate_entity_code(
                Customer, prefix='CUST', organization=request.organization
            )
        """
        # Build base query
        queryset = model.objects.all()
        if organization:
            queryset = OrganizationService.filter_queryset_by_org(queryset, organization)

        # Get max existing code with this prefix
        if hasattr(model, 'code'):
            code_field = 'code'
        elif hasattr(model, model.__name__.lower() + '_id'):
            code_field = model.__name__.lower() + '_id'
        else:
            raise ValueError(f"Cannot determine code field for {model.__name__}")

        # Find max numeric part
        max_code = 0
        for instance in queryset.filter(**{f"{code_field}__startswith": prefix}):
            code_value = getattr(instance, code_field, '')
            if code_value.startswith(prefix):
                try:
                    numeric_part = code_value[len(prefix):]
                    if numeric_part.isdigit():
                        max_code = max(max_code, int(numeric_part))
                except (ValueError, IndexError):
                    continue

        next_number = max_code + 1
        number_part = str(next_number).zfill(padding)

        code = f"{prefix}{number_part}{suffix}"

        # Ensure uniqueness
        while queryset.filter(**{code_field: code}).exists():
            next_number += 1
            number_part = str(next_number).zfill(padding)
            code = f"{prefix}{number_part}{suffix}"

        return code


class VoucherSequenceConfig(models.Model):
    """
    Configuration for voucher number sequences per organization and type.
    """

    PREFIX_CHOICES = [
        ('FY', 'Fiscal Year'),
        ('NONE', 'No Prefix'),
        ('CUSTOM', 'Custom'),
    ]

    RESET_CHOICES = [
        ('fiscal_year', 'Fiscal Year'),
        ('calendar_year', 'Calendar Year'),
        ('never', 'Never'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='voucher_sequences'
    )
    voucher_type = models.CharField(max_length=50)  # e.g., 'journal', 'invoice', 'payment'
    prefix_type = models.CharField(max_length=20, choices=PREFIX_CHOICES, default='FY')
    custom_prefix = models.CharField(max_length=20, blank=True)
    reset_policy = models.CharField(max_length=20, choices=RESET_CHOICES, default='fiscal_year')
    sequence_next = models.PositiveIntegerField(default=1)
    padding = models.PositiveIntegerField(default=4)
    separator = models.CharField(max_length=5, default='-')

    # Tracking
    last_reset_date = models.DateField(null=True, blank=True)
    last_fiscal_year = models.ForeignKey(
        'accounting.FiscalYear',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sequence_configs'
    )

    class Meta:
        unique_together = ('organization', 'voucher_type')
        ordering = ('organization', 'voucher_type')

    def __str__(self):
        return f"{self.organization.code} - {self.voucher_type}"

    @classmethod
    def get_or_create_config(cls, organization: Organization, voucher_type: str) -> 'VoucherSequenceConfig':
        """
        Get or create sequence config for the given org and voucher type.
        """
        config, created = cls.objects.get_or_create(
            organization=organization,
            voucher_type=voucher_type,
            defaults={
                'prefix_type': 'FY' if voucher_type in ['journal', 'invoice'] else 'NONE',
                'padding': 4,
                'separator': '-',
            }
        )
        return config

    def generate_number(self, date_obj: date, fiscal_year: Optional[Any] = None) -> str:
        """
        Generate the next voucher number.
        """
        with transaction.atomic():
            # Handle reset policy
            self._check_and_reset_sequence(date_obj, fiscal_year)

            # Build prefix
            prefix = self._build_prefix(date_obj, fiscal_year)

            # Get next sequence number
            sequence_num = self.sequence_next
            self.sequence_next += 1
            self.save(update_fields=['sequence_next'])

            # Format number
            number_part = str(sequence_num).zfill(self.padding)

            return f"{prefix}{self.separator}{number_part}"

    def _build_prefix(self, date_obj: date, fiscal_year: Optional[Any] = None) -> str:
        """Build the prefix part of the voucher number."""
        if self.prefix_type == 'NONE':
            return self.voucher_type.upper()[:3]
        elif self.prefix_type == 'FY':
            if fiscal_year:
                fy_code = fiscal_year.code
            else:
                # Try to get fiscal year for the date
                from accounting.models import FiscalYear
                fiscal_year = FiscalYear.get_for_date(self.organization, date_obj)
                fy_code = fiscal_year.code if fiscal_year else str(date_obj.year)
            return f"{fy_code}{self.voucher_type.upper()[:2]}"
        elif self.prefix_type == 'CUSTOM':
            return self.custom_prefix or self.voucher_type.upper()[:3]
        else:
            return self.voucher_type.upper()[:3]

    def _check_and_reset_sequence(self, date_obj: date, fiscal_year: Optional[Any] = None) -> None:
        """Check if sequence should be reset based on policy."""
        should_reset = False

        if self.reset_policy == 'fiscal_year':
            if fiscal_year:
                current_fy = fiscal_year
            else:
                from accounting.models import FiscalYear
                current_fy = FiscalYear.get_for_date(self.organization, date_obj)

            if current_fy and current_fy != self.last_fiscal_year:
                should_reset = True
                self.last_fiscal_year = current_fy

        elif self.reset_policy == 'calendar_year':
            current_year = date_obj.year
            if not self.last_reset_date or self.last_reset_date.year != current_year:
                should_reset = True
                self.last_reset_date = date_obj

        if should_reset:
            self.sequence_next = 1
            self.save(update_fields=['sequence_next', 'last_reset_date', 'last_fiscal_year'])


class AutoIncrementCodeGenerator:
    """
    Legacy auto-increment code generator using database sequences.
    """

    def __init__(self, model: models.Model, field: str, *, organization: Optional[Organization] = None,
                 prefix: str = '', suffix: str = '', padding: int = 2):
        self.model = model
        self.field = field
        self.organization = organization
        self.prefix = prefix
        self.suffix = suffix
        self.padding = padding

    def generate_code(self) -> str:
        """
        Generate the next sequential code using database sequences.
        """
        from accounting.models import AutoIncrementSequence

        with transaction.atomic():
            sequence, _ = AutoIncrementSequence.objects.select_for_update().get_or_create(
                organization=self.organization,
                model_label=self.model._meta.label_lower,
                field_name=self.field,
                defaults={'next_value': 1},
            )

            next_value = sequence.next_value
            sequence.next_value = next_value + 1
            sequence.save(update_fields=['next_value'])

        number = str(next_value).zfill(self.padding)
        return f"{self.prefix}{number}{self.suffix}"


# Template tags for sequence generation
def generate_next_code(prefix: str, organization: Organization, model: models.Model) -> str:
    """
    Template tag for generating codes in templates.

    Usage:
        {% load sequence_tags %}
        {% generate_next_code "ACC" organization account_model as next_code %}
        Next account code: {{ next_code }}
    """
    return SequenceGenerator.generate_entity_code(
        model, prefix=prefix, organization=organization
    )
