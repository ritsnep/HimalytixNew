"""
Cache Management Utilities

Provides centralized caching utilities for performance optimization,
cache invalidation strategies, and organization-aware caching.
"""

import hashlib
import json
from typing import Optional, Dict, List, Any, Tuple, Union, Callable
from datetime import datetime, timedelta

from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone

from .organization import OrganizationService


class CacheManager:
    """
    Centralized cache management with organization awareness and
    intelligent invalidation strategies.
    """

    # Cache key prefixes
    ACCOUNT_BALANCE = "account_balance"
    EXCHANGE_RATE = "exchange_rate"
    USER_PERMISSIONS = "user_permissions"
    ACCOUNT_TREE = "account_tree"
    FINANCIAL_REPORT = "financial_report"
    ORGANIZATION_DATA = "org_data"
    TAX_CALCULATION = "tax_calc"

    # Cache timeouts (in seconds)
    SHORT_TIMEOUT = 300    # 5 minutes
    MEDIUM_TIMEOUT = 1800  # 30 minutes
    LONG_TIMEOUT = 3600    # 1 hour
    DAY_TIMEOUT = 86400    # 24 hours

    @staticmethod
    def get_account_balance(account_id: int, organization_id: int) -> Optional[Decimal]:
        """
        Get cached account balance.

        Args:
            account_id: Account ID
            organization_id: Organization ID

        Returns:
            Cached balance or None
        """
        from decimal import Decimal

        key = CacheManager._make_key(
            CacheManager.ACCOUNT_BALANCE,
            account_id=account_id,
            organization_id=organization_id
        )

        cached = cache.get(key)
        return Decimal(str(cached)) if cached is not None else None

    @staticmethod
    def set_account_balance(account_id: int, organization_id: int, balance: Decimal) -> None:
        """
        Cache account balance.

        Args:
            account_id: Account ID
            organization_id: Organization ID
            balance: Balance to cache
        """
        key = CacheManager._make_key(
            CacheManager.ACCOUNT_BALANCE,
            account_id=account_id,
            organization_id=organization_id
        )

        cache.set(key, str(balance), CacheManager.MEDIUM_TIMEOUT)

    @staticmethod
    def get_exchange_rate(from_currency: str, to_currency: str, organization_id: Optional[int] = None) -> Optional[Decimal]:
        """
        Get cached exchange rate.

        Args:
            from_currency: Source currency code
            to_currency: Target currency code
            organization_id: Organization ID (optional)

        Returns:
            Cached exchange rate or None
        """
        from decimal import Decimal

        key = CacheManager._make_key(
            CacheManager.EXCHANGE_RATE,
            from_currency=from_currency,
            to_currency=to_currency,
            organization_id=organization_id
        )

        cached = cache.get(key)
        return Decimal(str(cached)) if cached is not None else None

    @staticmethod
    def set_exchange_rate(
        from_currency: str,
        to_currency: str,
        rate: Decimal,
        organization_id: Optional[int] = None
    ) -> None:
        """
        Cache exchange rate.

        Args:
            from_currency: Source currency code
            to_currency: Target currency code
            rate: Exchange rate to cache
            organization_id: Organization ID (optional)
        """
        key = CacheManager._make_key(
            CacheManager.EXCHANGE_RATE,
            from_currency=from_currency,
            to_currency=to_currency,
            organization_id=organization_id
        )

        cache.set(key, str(rate), CacheManager.LONG_TIMEOUT)

    @staticmethod
    def get_user_permissions(user_id: int, organization_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Get cached user permissions.

        Args:
            user_id: User ID
            organization_id: Organization ID (optional)

        Returns:
            Cached permissions dictionary or None
        """
        key = CacheManager._make_key(
            CacheManager.USER_PERMISSIONS,
            user_id=user_id,
            organization_id=organization_id
        )

        return cache.get(key)

    @staticmethod
    def set_user_permissions(user_id: int, permissions: Dict[str, Any], organization_id: Optional[int] = None) -> None:
        """
        Cache user permissions.

        Args:
            user_id: User ID
            permissions: Permissions dictionary to cache
            organization_id: Organization ID (optional)
        """
        key = CacheManager._make_key(
            CacheManager.USER_PERMISSIONS,
            user_id=user_id,
            organization_id=organization_id
        )

        cache.set(key, permissions, CacheManager.MEDIUM_TIMEOUT)

    @staticmethod
    def get_account_tree(organization_id: int, include_balances: bool = False) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached account tree.

        Args:
            organization_id: Organization ID
            include_balances: Whether tree includes balances

        Returns:
            Cached account tree or None
        """
        key = CacheManager._make_key(
            CacheManager.ACCOUNT_TREE,
            organization_id=organization_id,
            include_balances=include_balances
        )

        return cache.get(key)

    @staticmethod
    def set_account_tree(organization_id: int, tree: List[Dict[str, Any]], include_balances: bool = False) -> None:
        """
        Cache account tree.

        Args:
            organization_id: Organization ID
            tree: Account tree to cache
            include_balances: Whether tree includes balances
        """
        key = CacheManager._make_key(
            CacheManager.ACCOUNT_TREE,
            organization_id=organization_id,
            include_balances=include_balances
        )

        cache.set(key, tree, CacheManager.MEDIUM_TIMEOUT)

    @staticmethod
    def get_financial_report(
        report_type: str,
        organization_id: int,
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[Any]:
        """
        Get cached financial report.

        Args:
            report_type: Type of report (trial_balance, balance_sheet, etc.)
            organization_id: Organization ID
            params: Report parameters (dates, filters, etc.)

        Returns:
            Cached report data or None
        """
        params_hash = CacheManager._hash_params(params or {})
        key = CacheManager._make_key(
            CacheManager.FINANCIAL_REPORT,
            report_type=report_type,
            organization_id=organization_id,
            params_hash=params_hash
        )

        return cache.get(key)

    @staticmethod
    def set_financial_report(
        report_type: str,
        organization_id: int,
        report_data: Any,
        params: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Cache financial report.

        Args:
            report_type: Type of report
            organization_id: Organization ID
            report_data: Report data to cache
            params: Report parameters
        """
        params_hash = CacheManager._hash_params(params or {})
        key = CacheManager._make_key(
            CacheManager.FINANCIAL_REPORT,
            report_type=report_type,
            organization_id=organization_id,
            params_hash=params_hash
        )

        cache.set(key, report_data, CacheManager.SHORT_TIMEOUT)

    @staticmethod
    def invalidate_organization_cache(organization_id: int) -> None:
        """
        Invalidate all cache entries for an organization.

        Args:
            organization_id: Organization ID
        """
        # Pattern-based invalidation for organization-specific data
        patterns = [
            f"{CacheManager.ACCOUNT_BALANCE}:*:{organization_id}",
            f"{CacheManager.ACCOUNT_TREE}:{organization_id}:*",
            f"{CacheManager.FINANCIAL_REPORT}:*:{organization_id}:*",
            f"{CacheManager.ORGANIZATION_DATA}:{organization_id}:*",
        ]

        for pattern in patterns:
            CacheManager._delete_pattern(pattern)

    @staticmethod
    def invalidate_account_cache(account_id: int, organization_id: int) -> None:
        """
        Invalidate cache entries for a specific account.

        Args:
            account_id: Account ID
            organization_id: Organization ID
        """
        # Invalidate account balance
        balance_key = CacheManager._make_key(
            CacheManager.ACCOUNT_BALANCE,
            account_id=account_id,
            organization_id=organization_id
        )
        cache.delete(balance_key)

        # Invalidate account trees (since they include balances)
        tree_pattern = f"{CacheManager.ACCOUNT_TREE}:{organization_id}:*"
        CacheManager._delete_pattern(tree_pattern)

        # Invalidate financial reports that might include this account
        report_pattern = f"{CacheManager.FINANCIAL_REPORT}:*:{organization_id}:*"
        CacheManager._delete_pattern(report_pattern)

    @staticmethod
    def invalidate_user_permissions(user_id: int) -> None:
        """
        Invalidate cached permissions for a user.

        Args:
            user_id: User ID
        """
        permissions_pattern = f"{CacheManager.USER_PERMISSIONS}:{user_id}:*"
        CacheManager._delete_pattern(permissions_pattern)

    @staticmethod
    def invalidate_exchange_rates() -> None:
        """
        Invalidate all cached exchange rates.
        """
        CacheManager._delete_pattern(f"{CacheManager.EXCHANGE_RATE}:*")

    @staticmethod
    def _make_key(prefix: str, **kwargs) -> str:
        """
        Generate a cache key from prefix and parameters.

        Args:
            prefix: Cache key prefix
            **kwargs: Key components

        Returns:
            Cache key string
        """
        components = [prefix]
        for key, value in sorted(kwargs.items()):
            if value is not None:
                components.append(f"{key}={value}")
        return ":".join(str(c) for c in components)

    @staticmethod
    def _hash_params(params: Dict[str, Any]) -> str:
        """
        Generate a hash for complex parameters.

        Args:
            params: Parameters dictionary

        Returns:
            Hash string
        """
        # Sort keys for consistent hashing
        sorted_params = json.dumps(params, sort_keys=True, default=str)
        return hashlib.md5(sorted_params.encode()).hexdigest()[:8]

    @staticmethod
    def _delete_pattern(pattern: str) -> None:
        """
        Delete cache keys matching a pattern.

        Args:
            pattern: Pattern to match (simplified implementation)
        """
        # Note: This is a simplified pattern deletion
        # In production, you might want to use a more sophisticated
        # cache backend that supports pattern deletion, or maintain
        # a registry of keys to delete them individually

        # For Redis-like caches, you could use:
        # if hasattr(cache, 'delete_pattern'):
        #     cache.delete_pattern(pattern)
        # else:
        #     # Fallback: individual key deletion if you maintain a registry
        #     pass

        # For now, we'll rely on timeout-based expiration
        pass


class CachedResult:
    """
    Decorator for caching function results.
    """

    def __init__(
        self,
        timeout: int = None,
        key_prefix: str = "",
        organization_aware: bool = False,
        user_aware: bool = False
    ):
        self.timeout = timeout or CacheManager.MEDIUM_TIMEOUT
        self.key_prefix = key_prefix
        self.organization_aware = organization_aware
        self.user_aware = user_aware

    def __call__(self, func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            # Generate cache key
            key_components = [self.key_prefix or func.__name__]

            if self.organization_aware:
                # Assume first arg after self is organization
                org = kwargs.get('organization') or (args[1] if len(args) > 1 else None)
                if org:
                    key_components.append(f"org={getattr(org, 'id', org)}")

            if self.user_aware:
                # Assume first arg after self is user
                user = kwargs.get('user') or (args[1] if len(args) > 1 else None)
                if user:
                    key_components.append(f"user={getattr(user, 'id', user)}")

            # Add function arguments to key
            for i, arg in enumerate(args):
                if i == 0 and hasattr(func, '__self__'):  # Skip self
                    continue
                key_components.append(f"arg{i}={arg}")

            for key, value in sorted(kwargs.items()):
                if key not in ['organization', 'user']:  # Skip special params
                    key_components.append(f"{key}={value}")

            cache_key = ":".join(str(c) for c in key_components)

            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                return result

            # Execute function
            result = func(*args, **kwargs)

            # Cache result
            cache.set(cache_key, result, self.timeout)

            return result

        return wrapper


class CacheInvalidationManager:
    """
    Manages cache invalidation for model changes.
    """

    @staticmethod
    def setup_model_signals():
        """
        Set up Django signals for automatic cache invalidation.
        Call this in your AppConfig.ready() method.
        """
        # Account model changes
        from django.apps import apps
        Account = apps.get_model('accounting', 'ChartOfAccount', require_ready=False)
        if Account:
            post_save.connect(CacheInvalidationManager._invalidate_account_cache, sender=Account)
            post_delete.connect(CacheInvalidationManager._invalidate_account_cache, sender=Account)

        # Journal model changes
        Journal = apps.get_model('accounting', 'Journal', require_ready=False)
        if Journal:
            post_save.connect(CacheInvalidationManager._invalidate_journal_cache, sender=Journal)
            post_delete.connect(CacheInvalidationManager._invalidate_journal_cache, sender=Journal)

        # Currency exchange rate changes
        CurrencyExchangeRate = apps.get_model('accounting', 'CurrencyExchangeRate', require_ready=False)
        if CurrencyExchangeRate:
            post_save.connect(CacheInvalidationManager._invalidate_exchange_rate_cache, sender=CurrencyExchangeRate)
            post_delete.connect(CacheInvalidationManager._invalidate_exchange_rate_cache, sender=CurrencyExchangeRate)

    @staticmethod
    def _invalidate_account_cache(sender, instance, **kwargs):
        """Invalidate cache when account changes."""
        if hasattr(instance, 'organization_id'):
            CacheManager.invalidate_account_cache(instance.id, instance.organization_id)

    @staticmethod
    def _invalidate_journal_cache(sender, instance, **kwargs):
        """Invalidate cache when journal changes."""
        # Invalidate account balances affected by this journal
        if hasattr(instance, 'lines'):
            for line in instance.lines.all():
                if hasattr(line, 'account') and hasattr(line.account, 'organization_id'):
                    CacheManager.invalidate_account_cache(
                        line.account.id,
                        line.account.organization_id
                    )

        # Invalidate financial reports
        if hasattr(instance, 'organization_id'):
            CacheManager.invalidate_organization_cache(instance.organization_id)

    @staticmethod
    def _invalidate_exchange_rate_cache(sender, instance, **kwargs):
        """Invalidate cache when exchange rates change."""
        CacheManager.invalidate_exchange_rates()


class CacheStats:
    """
    Cache performance statistics and monitoring.
    """

    @staticmethod
    def get_cache_stats() -> Dict[str, Any]:
        """
        Get cache performance statistics.

        Returns:
            Dictionary with cache statistics
        """
        # This would integrate with your cache backend to get hit/miss rates
        # For now, return basic info
        return {
            'cache_backend': str(type(cache).__name__),
            'timeout_settings': {
                'short': CacheManager.SHORT_TIMEOUT,
                'medium': CacheManager.MEDIUM_TIMEOUT,
                'long': CacheManager.LONG_TIMEOUT,
                'day': CacheManager.DAY_TIMEOUT,
            },
            'key_prefixes': [
                CacheManager.ACCOUNT_BALANCE,
                CacheManager.EXCHANGE_RATE,
                CacheManager.USER_PERMISSIONS,
                CacheManager.ACCOUNT_TREE,
                CacheManager.FINANCIAL_REPORT,
            ]
        }

    @staticmethod
    def clear_expired_cache() -> int:
        """
        Clear expired cache entries.

        Returns:
            Number of entries cleared (if supported by backend)
        """
        # Most cache backends handle expiration automatically
        # This is a placeholder for manual cleanup if needed
        return 0


# Utility functions for common caching patterns
def cached_organization_data(timeout: int = None):
    """
    Decorator for caching organization-specific data.

    Usage:
        @cached_organization_data(timeout=1800)
        def get_org_settings(organization):
            # Expensive operation
            return settings
    """
    return CachedResult(
        timeout=timeout or CacheManager.MEDIUM_TIMEOUT,
        organization_aware=True
    )


def cached_user_data(timeout: int = None):
    """
    Decorator for caching user-specific data.

    Usage:
        @cached_user_data(timeout=900)
        def get_user_dashboard(user, organization):
            # Expensive dashboard calculation
            return dashboard_data
    """
    return CachedResult(
        timeout=timeout or CacheManager.SHORT_TIMEOUT,
        user_aware=True,
        organization_aware=True
    )


def invalidate_cache_on_change(model_class: type, fields_to_watch: Optional[List[str]] = None):
    """
    Decorator to invalidate cache when model fields change.

    Args:
        model_class: Django model class
        fields_to_watch: Specific fields to watch for changes

    Usage:
        @invalidate_cache_on_change(Account, ['current_balance'])
        def update_balance(account, new_balance):
            account.current_balance = new_balance
            account.save()
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Get instance before change
            if args and hasattr(args[0], 'pk'):
                old_instance = model_class.objects.get(pk=args[0].pk)
            else:
                old_instance = None

            # Execute function
            result = func(*args, **kwargs)

            # Get instance after change
            if args and hasattr(args[0], 'pk'):
                new_instance = model_class.objects.get(pk=args[0].pk)

                # Check if watched fields changed
                if fields_to_watch and old_instance:
                    changed = any(
                        getattr(old_instance, field, None) != getattr(new_instance, field, None)
                        for field in fields_to_watch
                    )
                    if changed:
                        # Invalidate relevant cache
                        if hasattr(new_instance, 'organization_id'):
                            CacheManager.invalidate_account_cache(
                                new_instance.pk, new_instance.organization_id
                            )

            return result
        return wrapper
    return decorator
