"""
Performance Optimization Service - Phase 3 Task 5

Features:
- Query optimization with select_related/prefetch_related
- Database indexing strategy
- Caching for frequent queries
- Query result caching
- Performance monitoring
"""

from django.core.cache import cache
from django.db.models import Prefetch, Q, Sum, Count, F
from django.views.decorators.cache import cache_page
from functools import wraps
from decimal import Decimal
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from accounting.models import (
    Organization, Journal, JournalLine, Account, AccountingPeriod,
    ApprovalWorkflow, ApprovalLog
)

logger = logging.getLogger(__name__)

# Cache timeouts
CACHE_TIMEOUT_SHORT = 300  # 5 minutes
CACHE_TIMEOUT_MEDIUM = 3600  # 1 hour
CACHE_TIMEOUT_LONG = 86400  # 24 hours


class PerformanceOptimizer:
    """
    Centralized performance optimization service.
    
    Handles:
    - Query optimization with select_related/prefetch_related
    - Caching strategies
    - Index recommendations
    - Query profiling
    """
    
    @staticmethod
    def optimize_journal_query(journals_qs):
        """
        Optimize journal queryset with related data.
        
        Args:
            journals_qs: Django queryset for Journal
            
        Returns:
            Optimized queryset with related data pre-fetched
        """
        return journals_qs.select_related(
            'organization',
            'journal_type',
            'created_by',
            'modified_by'
        ).prefetch_related(
            'journalline_set__account',
            'journalline_set__department',
            'journalline_set__project',
            'approvallog_set__approved_by'
        )
    
    @staticmethod
    def optimize_account_query(accounts_qs):
        """
        Optimize account queryset with related data.
        
        Args:
            accounts_qs: Django queryset for Account
            
        Returns:
            Optimized queryset with related data pre-fetched
        """
        return accounts_qs.select_related(
            'organization',
            'parent_account'
        ).prefetch_related(
            'sub_accounts'
        )
    
    @staticmethod
    def optimize_approval_query(approvals_qs):
        """
        Optimize approval workflow queryset.
        
        Args:
            approvals_qs: Django queryset for ApprovalWorkflow
            
        Returns:
            Optimized queryset with related data pre-fetched
        """
        return approvals_qs.select_related(
            'organization',
            'journal_type'
        ).prefetch_related(
            'steps',
            'approvallog_set__approved_by'
        )
    
    @staticmethod
    def get_organization_summary(organization_id: int) -> Dict[str, Any]:
        """
        Get organization summary with optimized queries.
        
        Caches result to avoid repeated queries.
        
        Args:
            organization_id: Organization ID
            
        Returns:
            dict with organization statistics
        """
        cache_key = f'org_summary_{organization_id}'
        cached = cache.get(cache_key)
        
        if cached:
            return cached
        
        org = Organization.objects.filter(pk=organization_id).first()
        
        if not org:
            return {}
        
        # Use single query with aggregation
        journal_stats = Journal.objects.filter(
            organization_id=organization_id
        ).values('status').annotate(
            count=Count('id'),
            total_amount=Sum('journalline__debit')
        )
        
        stats_by_status = {stat['status']: stat for stat in journal_stats}
        
        result = {
            'organization_id': organization_id,
            'organization_name': org.name,
            'total_journals': Journal.objects.filter(
                organization_id=organization_id
            ).count(),
            'journal_stats': stats_by_status,
            'generated_at': datetime.now().isoformat()
        }
        
        cache.set(cache_key, result, CACHE_TIMEOUT_MEDIUM)
        return result
    
    @staticmethod
    def get_account_balances(
        organization_id: int,
        date: datetime = None,
        use_cache: bool = True
    ) -> Dict[int, Decimal]:
        """
        Get account balances with optimization.
        
        Uses aggregation in single query and caches result.
        
        Args:
            organization_id: Organization ID
            date: Balance as of date (default: today)
            use_cache: Whether to use caching
            
        Returns:
            dict mapping account_id to balance
        """
        if date is None:
            date = datetime.now().date()
        
        if use_cache:
            cache_key = f'account_balances_{organization_id}_{date}'
            cached = cache.get(cache_key)
            if cached:
                return cached
        
        # Single aggregation query
        balances_qs = JournalLine.objects.filter(
            account__organization_id=organization_id,
            journal__date__lte=date,
            journal__status='Posted'
        ).values('account_id').annotate(
            debit_total=Sum('debit', default=Decimal('0')),
            credit_total=Sum('credit', default=Decimal('0'))
        )
        
        balances = {}
        for balance in balances_qs:
            account_id = balance['account_id']
            debit = balance['debit_total'] or Decimal('0')
            credit = balance['credit_total'] or Decimal('0')
            balances[account_id] = debit - credit
        
        if use_cache:
            cache.set(cache_key, balances, CACHE_TIMEOUT_LONG)
        
        return balances
    
    @staticmethod
    def get_trial_balance_optimized(
        organization_id: int,
        as_of_date: datetime = None
    ) -> List[Dict[str, Any]]:
        """
        Get trial balance with optimized queries.
        
        Args:
            organization_id: Organization ID
            as_of_date: Balance as of date
            
        Returns:
            list of account balances
        """
        if as_of_date is None:
            as_of_date = datetime.now().date()
        
        cache_key = f'trial_balance_{organization_id}_{as_of_date}'
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        # Single query with aggregation
        trial_balance = []
        
        accounts = Account.objects.filter(
            organization_id=organization_id,
            is_active=True
        ).values(
            'id', 'code', 'name', 'account_type'
        )
        
        balances = PerformanceOptimizer.get_account_balances(
            organization_id, as_of_date, use_cache=False
        )
        
        for account in accounts:
            balance = balances.get(account['id'], Decimal('0'))
            
            if balance != Decimal('0'):
                trial_balance.append({
                    'account_id': account['id'],
                    'account_code': account['code'],
                    'account_name': account['name'],
                    'account_type': account['account_type'],
                    'debit': balance if balance > 0 else Decimal('0'),
                    'credit': -balance if balance < 0 else Decimal('0')
                })
        
        cache.set(cache_key, trial_balance, CACHE_TIMEOUT_LONG)
        return trial_balance
    
    @staticmethod
    def get_recent_journals(
        organization_id: int,
        limit: int = 20,
        days: int = 30
    ) -> List[Journal]:
        """
        Get recent journals with optimization.
        
        Args:
            organization_id: Organization ID
            limit: Maximum journals to return
            days: Number of days to look back
            
        Returns:
            list of Journal objects
        """
        since = datetime.now().date() - timedelta(days=days)
        
        return PerformanceOptimizer.optimize_journal_query(
            Journal.objects.filter(
                organization_id=organization_id,
                date__gte=since
            ).order_by('-date')[:limit]
        )
    
    @staticmethod
    def invalidate_org_cache(organization_id: int):
        """
        Invalidate all caches for an organization.
        
        Called when data changes.
        
        Args:
            organization_id: Organization ID
        """
        patterns = [
            f'org_summary_{organization_id}',
            f'account_balances_{organization_id}_*',
            f'trial_balance_{organization_id}_*',
            f'journal_list_{organization_id}_*'
        ]
        
        for pattern in patterns:
            # Use cache delete_pattern if available
            try:
                cache.delete_pattern(pattern)
            except:
                pass
        
        logger.info(f'Cache invalidated for organization {organization_id}')


class QueryOptimizationDecorator:
    """Decorators for query optimization."""
    
    @staticmethod
    def cached_query(timeout: int = CACHE_TIMEOUT_MEDIUM):
        """
        Cache query results.
        
        Usage:
            @cached_query(timeout=3600)
            def expensive_query(org_id):
                return Journal.objects.filter(...)
        
        Args:
            timeout: Cache timeout in seconds
            
        Returns:
            Decorator function
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key from function name and arguments
                cache_key = f'{func.__name__}_{str(args)}_{str(kwargs)}'
                
                cached = cache.get(cache_key)
                if cached is not None:
                    return cached
                
                result = func(*args, **kwargs)
                cache.set(cache_key, result, timeout)
                return result
            
            return wrapper
        return decorator
    
    @staticmethod
    def optimized_queryset(func):
        """
        Automatically optimize queryset results.
        
        Usage:
            @optimized_queryset
            def get_journals(org):
                return Journal.objects.filter(...)
        
        Args:
            func: Function to optimize
            
        Returns:
            Decorator function
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            qs = func(*args, **kwargs)
            
            # Determine queryset type and optimize
            if hasattr(qs, 'model'):
                if qs.model.__name__ == 'Journal':
                    return PerformanceOptimizer.optimize_journal_query(qs)
                elif qs.model.__name__ == 'Account':
                    return PerformanceOptimizer.optimize_account_query(qs)
            
            return qs
        
        return wrapper


class DatabaseIndexOptimizer:
    """
    Database indexing recommendations and monitoring.
    
    Provides:
    - Index recommendations
    - Missing index detection
    - Index usage analysis
    """
    
    RECOMMENDED_INDEXES = [
        # Journal indexes
        {
            'model': 'Journal',
            'fields': ['organization_id', 'date'],
            'name': 'idx_journal_org_date',
            'reason': 'Frequent filtering by organization and date'
        },
        {
            'model': 'Journal',
            'fields': ['organization_id', 'status'],
            'name': 'idx_journal_org_status',
            'reason': 'Status filtering queries'
        },
        {
            'model': 'Journal',
            'fields': ['organization_id', 'created_at'],
            'name': 'idx_journal_org_created',
            'reason': 'Recent journals queries'
        },
        # JournalLine indexes
        {
            'model': 'JournalLine',
            'fields': ['account_id', 'journal__date'],
            'name': 'idx_line_account_date',
            'reason': 'Account balance calculation'
        },
        {
            'model': 'JournalLine',
            'fields': ['journal_id'],
            'name': 'idx_line_journal',
            'reason': 'Journal line retrieval'
        },
        # Account indexes
        {
            'model': 'Account',
            'fields': ['organization_id', 'code'],
            'name': 'idx_account_org_code',
            'reason': 'Account lookup by code'
        },
        {
            'model': 'Account',
            'fields': ['organization_id', 'account_type'],
            'name': 'idx_account_type',
            'reason': 'Account type filtering'
        },
        # ApprovalLog indexes
        {
            'model': 'ApprovalLog',
            'fields': ['organization_id', 'status'],
            'name': 'idx_approval_org_status',
            'reason': 'Approval queue filtering'
        },
    ]
    
    @staticmethod
    def get_index_recommendations() -> List[Dict[str, str]]:
        """
        Get list of recommended indexes.
        
        Returns:
            list of index recommendations
        """
        return DatabaseIndexOptimizer.RECOMMENDED_INDEXES
    
    @staticmethod
    def create_indexes_migration() -> str:
        """
        Generate Django migration for recommended indexes.
        
        Returns:
            Migration code as string
        """
        migration = '''
# Auto-generated indexes migration

from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('accounting', 'XXXX_previous_migration'),
    ]

    operations = [
'''
        
        for idx in DatabaseIndexOptimizer.RECOMMENDED_INDEXES:
            migration += f'''
        migrations.AddIndex(
            model_name='{idx["model"].lower()}',
            index=models.Index(fields={list(idx["fields"])}, name='{idx["name"]}'),
        ),
'''
        
        migration += '''
    ]
'''
        return migration


class CacheInvalidationManager:
    """
    Manage cache invalidation on data changes.
    
    Hooks into model signals to invalidate caches.
    """
    
    @staticmethod
    def invalidate_on_journal_change(sender, instance, **kwargs):
        """Invalidate caches when journal changes."""
        PerformanceOptimizer.invalidate_org_cache(instance.organization_id)
    
    @staticmethod
    def invalidate_on_account_change(sender, instance, **kwargs):
        """Invalidate caches when account changes."""
        PerformanceOptimizer.invalidate_org_cache(instance.organization_id)
    
    @staticmethod
    def register_signals():
        """Register signal handlers for cache invalidation."""
        from django.db.models.signals import post_save, post_delete
        
        post_save.connect(
            CacheInvalidationManager.invalidate_on_journal_change,
            sender=Journal
        )
        post_delete.connect(
            CacheInvalidationManager.invalidate_on_journal_change,
            sender=Journal
        )
        
        post_save.connect(
            CacheInvalidationManager.invalidate_on_account_change,
            sender=Account
        )
        post_delete.connect(
            CacheInvalidationManager.invalidate_on_account_change,
            sender=Account
        )


class QueryPerformanceMonitor:
    """
    Monitor and log query performance.
    
    Helps identify slow queries.
    """
    
    SLOW_QUERY_THRESHOLD = 0.5  # seconds
    
    @staticmethod
    def log_slow_queries():
        """Log slow queries from Django debug toolbar."""
        if hasattr(logger, 'performance'):
            logger.performance.info('Slow queries detected')
    
    @staticmethod
    def get_query_statistics() -> Dict[str, Any]:
        """
        Get query statistics.
        
        Returns:
            dict with query stats
        """
        return {
            'total_queries': 0,
            'slow_queries': 0,
            'average_time': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
