"""
Validation Utilities

Provides centralized business rule validation for the accounting system.
Ensures data integrity and business logic compliance.
"""

from typing import Optional, Dict, List, Any, Tuple, Union
from decimal import Decimal
from datetime import date, datetime
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .organization import OrganizationService
from .currency import CurrencyConverter, CurrencyValidator
from .coa import COAValidator


class BusinessValidator:
    """
    Comprehensive business rule validation for accounting operations.
    """

    @staticmethod
    def validate_date_range(
        start_date: Any,
        end_date: Any,
        allow_future: bool = True,
        max_days: Optional[int] = None
    ) -> Tuple[bool, str]:
        """
        Validate date range with business rules.

        Args:
            start_date: Start date
            end_date: End date
            allow_future: Whether future dates are allowed
            max_days: Maximum allowed days between dates

        Returns:
            Tuple of (is_valid, error_message)

        Usage:
            # Validate fiscal year dates
            is_valid, error = BusinessValidator.validate_date_range(
                fy.start_date, fy.end_date, allow_future=False, max_days=366
            )
        """
        if not start_date or not end_date:
            return False, "Both start and end dates are required"

        # Ensure they are date objects
        if isinstance(start_date, str):
            start_date = date.fromisoformat(start_date)
        if isinstance(end_date, str):
            end_date = date.fromisoformat(end_date)

        # Basic order validation
        if start_date >= end_date:
            return False, "Start date must be before end date"

        # Future date validation
        today = timezone.localdate()
        if not allow_future:
            if start_date > today or end_date > today:
                return False, "Future dates are not allowed"

        # Maximum range validation
        if max_days:
            days_diff = (end_date - start_date).days
            if days_diff > max_days:
                return False, f"Date range cannot exceed {max_days} days"

        return True, ""

    @staticmethod
    def validate_account_balance(
        account: Any,
        amount: Decimal,
        transaction_type: str,
        organization: Optional[Any] = None
    ) -> Tuple[bool, str]:
        """
        Validate account balance operations.

        Args:
            account: Account object
            amount: Transaction amount
            transaction_type: Type of transaction ('debit', 'credit')
            organization: Organization for context

        Returns:
            Tuple of (is_valid, error_message)

        Usage:
            # Before posting a transaction
            is_valid, error = BusinessValidator.validate_account_balance(
                account, Decimal('100'), 'debit', request.organization
            )
        """
        if not account:
            return False, "Account is required"

        if amount <= 0:
            return False, "Amount must be positive"

        # Check account type constraints
        if hasattr(account, 'account_type'):
            account_type = account.account_type

            # Control accounts may have special rules
            if hasattr(account, 'is_control_account') and account.is_control_account:
                if hasattr(account, 'control_account_type'):
                    control_type = account.control_account_type
                    # Add control account specific validations here

            # Check if account allows manual entries
            if hasattr(account, 'allow_manual_journal') and not account.allow_manual_journal:
                return False, "Account does not allow manual journal entries"

        return True, ""

    @staticmethod
    def validate_fiscal_year_period(
        target_date: Any,
        organization: Any
    ) -> Tuple[bool, str]:
        """
        Validate that date falls within an open fiscal year period.

        Args:
            target_date: Date to validate
            organization: Organization instance

        Returns:
            Tuple of (is_valid, error_message)

        Usage:
            # Before creating transactions
            is_valid, error = BusinessValidator.validate_fiscal_year_period(
                transaction_date, request.organization
            )
        """
        if not target_date:
            return False, "Date is required"

        if not organization:
            return False, "Organization is required"

        # Get fiscal year for the date
        from accounting.models import FiscalYear
        fiscal_year = FiscalYear.get_for_date(organization, target_date)

        if not fiscal_year:
            return False, f"No fiscal year found for date {target_date}"

        if fiscal_year.status != 'open':
            return False, f"Fiscal year {fiscal_year.code} is {fiscal_year.status}"

        # Check if date is within accounting period
        from accounting.models import AccountingPeriod
        is_in_open_period = AccountingPeriod.is_date_in_open_period(organization, target_date)

        if not is_in_open_period:
            return False, f"Date {target_date} is not in an open accounting period"

        return True, ""

    @staticmethod
    def validate_journal_balance(lines: List[Dict[str, Any]]) -> Tuple[bool, str]:
        """
        Validate that journal lines balance (debits = credits).

        Args:
            lines: List of journal line dictionaries with 'debit_amount', 'credit_amount'

        Returns:
            Tuple of (is_valid, error_message)

        Usage:
            # Before posting journal
            lines_data = [
                {'debit_amount': 100, 'credit_amount': 0},
                {'debit_amount': 0, 'credit_amount': 100}
            ]
            is_valid, error = BusinessValidator.validate_journal_balance(lines_data)
        """
        if not lines:
            return False, "Journal must have at least one line"

        total_debit = Decimal('0')
        total_credit = Decimal('0')

        for line in lines:
            debit = line.get('debit_amount') or line.get('debit') or Decimal('0')
            credit = line.get('credit_amount') or line.get('credit') or Decimal('0')

            # Ensure line has either debit or credit, not both
            if debit > 0 and credit > 0:
                return False, "Journal line cannot have both debit and credit amounts"

            if debit < 0 or credit < 0:
                return False, "Amounts cannot be negative"

            total_debit += Decimal(str(debit))
            total_credit += Decimal(str(credit))

        # Check if balanced
        imbalance = abs(total_debit - total_credit)
        if imbalance > Decimal('0.01'):  # Allow small rounding differences
            return False, f"Journal is not balanced. Debits: {total_debit}, Credits: {total_credit}"

        return True, ""

    @staticmethod
    def validate_transaction_amounts(
        transactions: List[Dict[str, Any]],
        max_amount: Optional[Decimal] = None,
        currency_code: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Validate transaction amounts against business rules.

        Args:
            transactions: List of transaction dictionaries
            max_amount: Maximum allowed amount per transaction
            currency_code: Expected currency code

        Returns:
            Tuple of (is_valid, error_message)
        """
        for i, txn in enumerate(transactions):
            amount = txn.get('amount')
            txn_currency = txn.get('currency_code') or txn.get('currency')

            if amount is None:
                return False, f"Transaction {i+1}: Amount is required"

            amount = Decimal(str(amount))
            if amount <= 0:
                return False, f"Transaction {i+1}: Amount must be positive"

            if max_amount and amount > max_amount:
                return False, f"Transaction {i+1}: Amount exceeds maximum allowed ({max_amount})"

            if currency_code and txn_currency and txn_currency != currency_code:
                return False, f"Transaction {i+1}: Currency mismatch (expected {currency_code})"

        return True, ""

    @staticmethod
    def validate_account_permissions(
        user: Any,
        account: Any,
        action: str,
        organization: Any
    ) -> Tuple[bool, str]:
        """
        Validate user permissions for account operations.

        Args:
            user: User instance
            account: Account instance
            action: Action being performed ('view', 'edit', 'delete', etc.)
            organization: Organization instance

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not user or not account:
            return False, "User and account are required"

        # Check organization access
        from .organization import OrganizationService
        if not OrganizationService.validate_org_access(user, organization):
            return False, "User does not have access to this organization"

        # Check account-specific permissions
        # This would integrate with your permission system
        # For now, basic checks:

        if action in ['edit', 'delete'] and hasattr(account, 'is_active') and not account.is_active:
            return False, "Cannot modify inactive accounts"

        if action == 'delete' and hasattr(account, 'is_system_account') and account.is_system_account:
            return False, "Cannot delete system accounts"

        return True, ""


class AccountingValidator:
    """
    Specialized validation for accounting operations.
    """

    @staticmethod
    def validate_voucher_number(
        voucher_type: str,
        number: str,
        organization: Any
    ) -> Tuple[bool, str]:
        """
        Validate voucher number format and uniqueness.

        Args:
            voucher_type: Type of voucher
            number: Voucher number to validate
            organization: Organization instance

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not number or not number.strip():
            return False, "Voucher number is required"

        # Check format based on type
        import re
        patterns = {
            'journal': r'^[A-Z]{2,3}-[A-Z]{2}\d{4,6}$',  # e.g., FY-JN000001
            'invoice': r'^[A-Z]{2,3}-[A-Z]{2}\d{4,6}$',   # e.g., FY-SI000001
            'payment': r'^[A-Z]{2,3}-[A-Z]{2}\d{4,6}$',   # e.g., FY-PY000001
        }

        pattern = patterns.get(voucher_type, r'^[A-Z0-9-]+$')
        if not re.match(pattern, number.upper()):
            return False, f"Invalid voucher number format for {voucher_type}"

        # Check uniqueness within organization
        from accounting.models import Journal
        exists = Journal.objects.filter(
            organization=organization,
            journal_number__iexact=number
        ).exists()

        if exists:
            return False, f"Voucher number {number} already exists"

        return True, ""

    @staticmethod
    def validate_exchange_rate(
        from_currency: str,
        to_currency: str,
        rate: Decimal,
        date: Optional[Any] = None
    ) -> Tuple[bool, str]:
        """
        Validate exchange rate values.

        Args:
            from_currency: Source currency code
            to_currency: Target currency code
            rate: Exchange rate value
            date: Date for the rate

        Returns:
            Tuple of (is_valid, error_message)
        """
        return CurrencyValidator.validate_exchange_rate(rate)

    @staticmethod
    def validate_period_lock(
        date: Any,
        organization: Any,
        action: str = 'modify'
    ) -> Tuple[bool, str]:
        """
        Validate that period is not locked for modifications.

        Args:
            date: Transaction date
            organization: Organization instance
            action: Action being attempted

        Returns:
            Tuple of (is_valid, error_message)
        """
        from accounting.models import AccountingPeriod

        try:
            period = AccountingPeriod.objects.get(
                organization=organization,
                start_date__lte=date,
                end_date__gte=date
            )

            if period.status == 'closed':
                return False, f"Cannot {action} transactions in closed period {period.name}"

            if period.status == 'adjustment' and action not in ['view', 'adjustment']:
                return False, f"Period {period.name} is in adjustment mode"

        except AccountingPeriod.DoesNotExist:
            return False, f"No accounting period found for date {date}"

        return True, ""


class DataIntegrityValidator:
    """
    Validation for data integrity and consistency.
    """

    @staticmethod
    def validate_foreign_key_integrity(model: models.Model, field_name: str) -> Tuple[bool, str]:
        """
        Validate foreign key relationships.

        Args:
            model: Model instance
            field_name: Foreign key field name

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            field = model._meta.get_field(field_name)
            if not isinstance(field, models.ForeignKey):
                return False, f"Field {field_name} is not a foreign key"

            related_value = getattr(model, field_name)
            if related_value is None and not field.null:
                return False, f"Required foreign key {field_name} is null"

            if related_value and not field.related_model.objects.filter(pk=related_value.pk).exists():
                return False, f"Referenced {field.related_model.__name__} does not exist"

        except Exception as e:
            return False, f"Foreign key validation error: {str(e)}"

        return True, ""

    @staticmethod
    def validate_unique_constraints(model: models.Model) -> Tuple[bool, str]:
        """
        Validate unique constraints on model.

        Args:
            model: Model instance

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not model.pk:  # Only validate on existing records
            return True, ""

        for constraint in model._meta.constraints:
            if isinstance(constraint, models.UniqueConstraint):
                # Check unique constraints
                fields = constraint.fields
                filter_kwargs = {field: getattr(model, field) for field in fields}

                # Exclude current instance
                existing = model.__class__.objects.filter(**filter_kwargs).exclude(pk=model.pk)

                if constraint.condition:
                    # Handle conditional unique constraints
                    existing = existing.filter(constraint.condition)

                if existing.exists():
                    field_names = ', '.join(fields)
                    return False, f"Unique constraint violation: {field_names}"

        return True, ""

    @staticmethod
    def validate_circular_references(
        model: models.Model,
        parent_field: str,
        max_depth: int = 10
    ) -> Tuple[bool, str]:
        """
        Validate for circular references in hierarchical data.

        Args:
            model: Model instance with parent relationship
            parent_field: Name of the parent field
            max_depth: Maximum allowed depth

        Returns:
            Tuple of (is_valid, error_message)
        """
        current = model
        visited = set()
        depth = 0

        while current and depth < max_depth:
            if current.pk in visited:
                return False, "Circular reference detected"

            visited.add(current.pk)
            current = getattr(current, parent_field)
            depth += 1

        if depth >= max_depth:
            return False, f"Maximum hierarchy depth ({max_depth}) exceeded"

        return True, ""


# Utility functions for common validation patterns
def validate_required_fields(instance: models.Model, required_fields: List[str]) -> None:
    """
    Validate that required fields are not empty.

    Args:
        instance: Model instance
        required_fields: List of field names

    Raises:
        ValidationError: If any required field is empty
    """
    errors = {}
    for field_name in required_fields:
        value = getattr(instance, field_name)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors[field_name] = f"This field is required."

    if errors:
        raise ValidationError(errors)


def validate_positive_amount(amount: Decimal, field_name: str = "amount") -> None:
    """
    Validate that amount is positive.

    Args:
        amount: Amount to validate
        field_name: Field name for error message

    Raises:
        ValidationError: If amount is not positive
    """
    if amount is None or amount <= 0:
        raise ValidationError({field_name: "Amount must be positive."})


def validate_date_not_future(date_value: Any, field_name: str = "date") -> None:
    """
    Validate that date is not in the future.

    Args:
        date_value: Date to validate
        field_name: Field name for error message

    Raises:
        ValidationError: If date is in the future
    """
    if date_value and date_value > timezone.localdate():
        raise ValidationError({field_name: "Date cannot be in the future."})
