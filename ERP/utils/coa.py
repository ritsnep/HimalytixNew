"""
Chart of Accounts (COA) Utilities

Provides comprehensive utilities for managing chart of accounts,
account hierarchies, balances, and account operations.
"""

from typing import Optional, Dict, List, Any, Tuple, Union
from decimal import Decimal
from django.db import models, transaction
from django.db.models import Sum, Q, F, Case, When, Value
from django.core.exceptions import ValidationError
from django.utils import timezone

from .organization import OrganizationService
from usermanagement.models import Organization


class COAService:
    """
    Comprehensive service for Chart of Accounts operations.

    Handles account trees, balances, validation, and hierarchical operations.
    """

    @staticmethod
    def get_account_tree(
        organization: Organization,
        include_balances: bool = False,
        as_of_date: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Get hierarchical account tree for an organization.

        Args:
            organization: Organization instance
            include_balances: Whether to include current balances
            as_of_date: Date for balance calculation (defaults to current)

        Returns:
            List of account dictionaries with hierarchy

        Usage:
            # In views
            tree = COAService.get_account_tree(request.organization, include_balances=True)
            return JsonResponse({'accounts': tree})
        """
        from accounting.models import ChartOfAccount

        # Get all active accounts for the organization
        accounts = ChartOfAccount.active_accounts.for_org(organization)

        if not accounts.exists():
            return []

        # Build tree structure
        account_map = {}
        root_accounts = []

        # First pass: create all account objects
        for account in accounts:
            account_data = {
                'id': account.pk,
                'code': account.account_code,
                'name': account.account_name,
                'type': account.account_type.name if account.account_type else '',
                'nature': account.account_type.nature if account.account_type else '',
                'level': account.account_level,
                'is_active': account.is_active,
                'children': [],
                'balance': Decimal('0'),
                'path': account.tree_path or account.account_code,
            }

            if include_balances:
                account_data['balance'] = COAService.get_account_balance(
                    account, as_of_date
                )

            account_map[account.pk] = account_data

        # Second pass: build hierarchy
        for account in accounts:
            if account.parent_account_id:
                # Child account
                parent = account_map.get(account.parent_account_id)
                if parent:
                    parent['children'].append(account_map[account.pk])
            else:
                # Root account
                root_accounts.append(account_map[account.pk])

        # Sort children by account code
        def sort_children(account_data):
            account_data['children'].sort(key=lambda x: x['code'])
            for child in account_data['children']:
                sort_children(child)

        for root in root_accounts:
            sort_children(root)

        return root_accounts

    @staticmethod
    def validate_account_code(code: str, organization: Organization) -> Tuple[bool, str]:
        """
        Validate an account code format and uniqueness.

        Args:
            code: Account code to validate
            organization: Organization instance

        Returns:
            Tuple of (is_valid, error_message)

        Usage:
            # In forms or APIs
            is_valid, error = COAService.validate_account_code(code, organization)
            if not is_valid:
                raise ValidationError(error)
        """
        from accounting.models import ChartOfAccount

        # Check format (should be numbers with optional dots)
        import re
        if not re.match(r'^\d+(\.\d{2})*$', code):
            return False, "Account code must be in format like 1000, 1000.01, 1000.01.01"

        # Check uniqueness within organization
        existing = ChartOfAccount.objects.filter(
            organization=organization,
            account_code=code
        ).exists()

        if existing:
            return False, f"Account code {code} already exists in this organization"

        return True, ""

    @staticmethod
    def get_child_accounts(parent_account: Any, include_self: bool = False) -> models.QuerySet:
        """
        Get all child accounts under a parent account.

        Args:
            parent_account: Parent ChartOfAccount instance
            include_self: Whether to include the parent account itself

        Returns:
            QuerySet of child accounts

        Usage:
            # Get all accounts under Assets
            asset_accounts = COAService.get_child_accounts(asset_account)
        """
        from accounting.models import ChartOfAccount

        if not parent_account:
            return ChartOfAccount.objects.none()

        # Use tree path for efficient querying
        path_prefix = parent_account.tree_path + '/' if parent_account.tree_path else parent_account.account_code + '/'

        queryset = ChartOfAccount.objects.filter(
            organization=parent_account.organization,
            tree_path__startswith=path_prefix
        )

        if include_self:
            queryset = queryset | ChartOfAccount.objects.filter(pk=parent_account.pk)

        return queryset.order_by('tree_path')

    @staticmethod
    def get_account_balance(
        account: Any,
        as_of_date: Optional[Any] = None,
        include_children: bool = True
    ) -> Decimal:
        """
        Calculate account balance as of a specific date.

        Args:
            account: ChartOfAccount instance
            as_of_date: Date for balance calculation (defaults to current)
            include_children: Whether to include child account balances

        Returns:
            Account balance as Decimal

        Usage:
            # Get current balance including children
            balance = COAService.get_account_balance(account, include_children=True)
        """
        if not account:
            return Decimal('0')

        as_of_date = as_of_date or timezone.now().date()

        # Get base balance from account
        balance = account.current_balance or Decimal('0')

        if include_children:
            # Add balances from child accounts
            child_accounts = COAService.get_child_accounts(account)
            child_balance_agg = child_accounts.aggregate(
                total_balance=Sum('current_balance')
            )
            child_balance = child_balance_agg.get('total_balance') or Decimal('0')
            balance += child_balance

        return balance

    @staticmethod
    def get_account_transactions(
        account: Any,
        start_date: Optional[Any] = None,
        end_date: Optional[Any] = None,
        include_children: bool = True
    ) -> models.QuerySet:
        """
        Get all transactions for an account within a date range.

        Args:
            account: ChartOfAccount instance
            start_date: Start date for filtering
            end_date: End date for filtering
            include_children: Whether to include child accounts

        Returns:
            QuerySet of GeneralLedger entries

        Usage:
            # Get account transactions for a period
            transactions = COAService.get_account_transactions(
                account, start_date, end_date
            )
        """
        from accounting.models import GeneralLedger

        if not account:
            return GeneralLedger.objects.none()

        # Base query for the account
        query = Q(account=account)

        if include_children:
            # Include child accounts
            child_accounts = COAService.get_child_accounts(account)
            child_ids = list(child_accounts.values_list('pk', flat=True))
            if child_ids:
                query |= Q(account_id__in=child_ids)

        # Apply date filtering
        if start_date:
            query &= Q(transaction_date__gte=start_date)
        if end_date:
            query &= Q(transaction_date__lte=end_date)

        return GeneralLedger.objects.filter(query).order_by('transaction_date')

    @staticmethod
    def create_account(
        organization: Organization,
        account_type: Any,
        name: str,
        parent_account: Optional[Any] = None,
        **kwargs
    ) -> Any:
        """
        Create a new chart of account with proper validation.

        Args:
            organization: Organization instance
            account_type: AccountType instance
            name: Account name
            parent_account: Parent account (optional)
            **kwargs: Additional account fields

        Returns:
            Created ChartOfAccount instance

        Usage:
            # Create a new expense account
            account = COAService.create_account(
                organization=org,
                account_type=expense_type,
                name="Office Supplies",
                description="Stationery and office supplies"
            )
        """
        from accounting.models import ChartOfAccount
        from .sequences import SequenceGenerator

        with transaction.atomic():
            # Generate account code
            account_code = SequenceGenerator.generate_account_code(
                account_type, parent_account, organization
            )

            # Create the account
            account = ChartOfAccount.objects.create(
                organization=organization,
                account_type=account_type,
                account_code=account_code,
                account_name=name,
                parent_account=parent_account,
                **kwargs
            )

            return account

    @staticmethod
    def move_account(account: Any, new_parent: Optional[Any] = None) -> None:
        """
        Move an account to a new parent, updating tree paths.

        Args:
            account: ChartOfAccount to move
            new_parent: New parent account (None for root level)

        Usage:
            # Move account under a different parent
            COAService.move_account(account, new_parent_account)
        """
        from accounting.models import ChartOfAccount

        with transaction.atomic():
            old_parent = account.parent_account
            account.parent_account = new_parent

            # Update tree path
            if new_parent:
                account.tree_path = f"{new_parent.tree_path}/{account.account_code}" if new_parent.tree_path else account.account_code
            else:
                account.tree_path = account.account_code

            account.save()

            # Update all child account paths
            COAService._update_child_paths(account)

    @staticmethod
    def _update_child_paths(parent_account: Any) -> None:
        """Update tree paths for all child accounts after parent move."""
        from accounting.models import ChartOfAccount

        children = COAService.get_child_accounts(parent_account, include_self=False)

        for child in children:
            if parent_account.tree_path:
                # Replace the old parent path with new parent path
                old_prefix = child.tree_path.split('/')[0] + '/'
                new_path = f"{parent_account.tree_path}/{child.account_code}"
                child.tree_path = new_path
            else:
                child.tree_path = child.account_code

            child.save()

    @staticmethod
    def get_account_summary(
        organization: Organization,
        account_type: Optional[str] = None,
        include_balances: bool = True
    ) -> Dict[str, Any]:
        """
        Get summary statistics for accounts in an organization.

        Args:
            organization: Organization instance
            account_type: Filter by account type nature (optional)
            include_balances: Whether to include balance totals

        Returns:
            Dictionary with account statistics

        Usage:
            # Get asset account summary
            summary = COAService.get_account_summary(org, 'asset', include_balances=True)
        """
        from accounting.models import ChartOfAccount

        accounts = ChartOfAccount.active_accounts.for_org(organization)

        if account_type:
            accounts = accounts.filter(account_type__nature=account_type)

        summary = {
            'total_accounts': accounts.count(),
            'active_accounts': accounts.filter(is_active=True).count(),
            'inactive_accounts': accounts.filter(is_active=False).count(),
        }

        if include_balances:
            balance_agg = accounts.aggregate(
                total_debit=Sum('current_balance', filter=Q(current_balance__gt=0)),
                total_credit=Sum('current_balance', filter=Q(current_balance__lt=0)),
                total_balance=Sum('current_balance')
            )

            summary.update({
                'total_debit_balance': abs(balance_agg.get('total_debit') or Decimal('0')),
                'total_credit_balance': abs(balance_agg.get('total_credit') or Decimal('0')),
                'net_balance': balance_agg.get('total_balance') or Decimal('0'),
            })

        return summary

    @staticmethod
    def search_accounts(
        organization: Organization,
        query: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search accounts by code or name.

        Args:
            organization: Organization instance
            query: Search query
            limit: Maximum results to return

        Returns:
            List of account dictionaries

        Usage:
            # Search for accounts containing "cash"
            results = COAService.search_accounts(org, "cash", limit=10)
        """
        from accounting.models import ChartOfAccount

        if not query or len(query.strip()) < 2:
            return []

        search_query = query.strip()
        accounts = ChartOfAccount.active_accounts.for_org(organization).filter(
            Q(account_code__icontains=search_query) |
            Q(account_name__icontains=search_query)
        )[:limit]

        return [{
            'id': acc.pk,
            'code': acc.account_code,
            'name': acc.account_name,
            'type': acc.account_type.name if acc.account_type else '',
            'balance': acc.current_balance or Decimal('0'),
        } for acc in accounts]

    @staticmethod
    def validate_account_hierarchy(account: Any) -> Tuple[bool, str]:
        """
        Validate account hierarchy constraints.

        Args:
            account: ChartOfAccount instance

        Returns:
            Tuple of (is_valid, error_message)

        Usage:
            # Before saving an account
            is_valid, error = COAService.validate_account_hierarchy(account)
        """
        # Check for circular references
        if account.parent_account:
            ancestor = account.parent_account
            visited = set()
            while ancestor:
                if ancestor.pk in visited:
                    return False, "Circular reference detected in account hierarchy"
                visited.add(ancestor.pk)
                ancestor = ancestor.parent_account

        # Check depth limit
        depth = 1
        parent = account.parent_account
        while parent:
            depth += 1
            if depth > 10:  # Max depth from settings
                return False, "Account hierarchy depth exceeds maximum allowed level"
            parent = parent.parent_account

        return True, ""

    @staticmethod
    def get_account_types_by_nature(organization: Organization) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get account types organized by nature for UI display.

        Args:
            organization: Organization instance

        Returns:
            Dictionary organized by account nature

        Usage:
            # For account creation forms
            account_types = COAService.get_account_types_by_nature(org)
        """
        from accounting.models import AccountType

        account_types = AccountType.objects.filter(is_active=True).order_by('nature', 'display_order')

        result = {}
        for at in account_types:
            nature = at.nature
            if nature not in result:
                result[nature] = []

            result[nature].append({
                'id': at.pk,
                'code': at.code,
                'name': at.name,
                'classification': at.classification,
            })

        return result


class COAValidator:
    """
    Validation utilities specific to Chart of Accounts.
    """

    @staticmethod
    def validate_account_code_format(code: str) -> bool:
        """Validate account code format (numbers with dots)."""
        import re
        return bool(re.match(r'^\d+(\.\d{2})*$', code))

    @staticmethod
    def validate_parent_child_relationship(parent: Any, child: Any) -> Tuple[bool, str]:
        """Validate that parent and child accounts are compatible."""
        if not parent or not child:
            return True, ""

        # Parent should not be a child of the child
        if parent.parent_account and parent.parent_account.pk == child.pk:
            return False, "Cannot set child account as parent"

        # Parent and child should have compatible account types
        if parent.account_type and child.account_type:
            if parent.account_type.nature != child.account_type.nature:
                return False, f"Parent and child must have same nature ({parent.account_type.nature})"

        return True, ""

    @staticmethod
    def validate_account_balance_operations(account: Any, amount: Decimal, operation: str) -> Tuple[bool, str]:
        """Validate balance-related operations."""
        if operation not in ['debit', 'credit']:
            return False, "Invalid operation type"

        # Add business rules as needed
        # e.g., check if account allows manual entries
        if not account.allow_manual_journal:
            return False, "Account does not allow manual journal entries"

        return True, ""


# Template widget for account selection
class AccountTypeaheadWidget:
    """
    Template widget for account typeahead selection.
    """

    template_name = "widgets/account_typeahead.html"

    def __init__(self, organization: Organization, url: str = None, **kwargs):
        self.organization = organization
        self.url = url or "/accounting/accounts/search/"
        self.attrs = kwargs

    def get_context(self, name: str, value: Any, attrs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get context for template rendering."""
        context = {
            'name': name,
            'value': value,
            'organization_id': self.organization.pk if self.organization else None,
            'search_url': self.url,
            'attrs': attrs or {},
        }
        return context
