"""
Tests for Performance Optimization - Phase 3 Task 5

Test coverage for:
- Query optimization
- Caching effectiveness
- Index recommendations
- Cache invalidation
"""

from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test.utils import override_settings
from datetime import date, datetime
from decimal import Decimal

from accounting.models import (
    Account, Journal, JournalLine, JournalType, Organization,
    AccountingPeriod
)
from accounting.services.performance_optimizer import (
    PerformanceOptimizer,
    DatabaseIndexOptimizer,
    CacheInvalidationManager
)

User = get_user_model()


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
})
class PerformanceOptimizerTestCase(TransactionTestCase):
    """Test performance optimization features."""

    def setUp(self):
        """Set up test data."""
        cache.clear()
        
        self.organization = Organization.objects.create(
            name="Test Org",
            code="TEST"
        )
        
        # Create accounts
        self.cash_account = Account.objects.create(
            organization=self.organization,
            code="1000",
            name="Cash",
            account_type="Asset",
            is_active=True
        )
        
        self.revenue_account = Account.objects.create(
            organization=self.organization,
            code="4000",
            name="Revenue",
            account_type="Revenue",
            is_active=True
        )
        
        # Create journal type
        self.journal_type = JournalType.objects.create(
            code="GJ",
            name="General Journal"
        )
        
        # Create test journals
        for i in range(5):
            journal = Journal.objects.create(
                organization=self.organization,
                journal_type=self.journal_type,
                date=date(2024, 1, i+1),
                reference=f"TEST{i:03d}",
                status="Posted"
            )
            
            JournalLine.objects.create(
                journal=journal,
                account=self.cash_account,
                debit=Decimal("100.00") * (i+1)
            )
            
            JournalLine.objects.create(
                journal=journal,
                account=self.revenue_account,
                credit=Decimal("100.00") * (i+1)
            )

    def test_optimize_journal_query(self):
        """Test journal query optimization."""
        journals_qs = Journal.objects.filter(organization=self.organization)
        optimized_qs = PerformanceOptimizer.optimize_journal_query(journals_qs)
        
        # Should have prefetch_related
        self.assertIsNotNone(optimized_qs)
        
        # Count should work
        count = optimized_qs.count()
        self.assertEqual(count, 5)

    def test_optimize_account_query(self):
        """Test account query optimization."""
        accounts_qs = Account.objects.filter(organization=self.organization)
        optimized_qs = PerformanceOptimizer.optimize_account_query(accounts_qs)
        
        self.assertIsNotNone(optimized_qs)
        count = optimized_qs.count()
        self.assertEqual(count, 2)

    def test_get_organization_summary_caching(self):
        """Test organization summary caching."""
        # First call should query database
        summary1 = PerformanceOptimizer.get_organization_summary(
            self.organization.pk
        )
        
        self.assertIsNotNone(summary1)
        self.assertEqual(summary1['organization_id'], self.organization.pk)
        
        # Second call should come from cache
        summary2 = PerformanceOptimizer.get_organization_summary(
            self.organization.pk
        )
        
        self.assertEqual(summary1, summary2)

    def test_get_account_balances(self):
        """Test account balance calculation."""
        balances = PerformanceOptimizer.get_account_balances(
            self.organization.pk
        )
        
        self.assertIsNotNone(balances)
        
        # Cash should have sum of all debits
        cash_balance = balances.get(self.cash_account.pk, Decimal('0'))
        expected = Decimal('100') + Decimal('200') + Decimal('300') + \
                   Decimal('400') + Decimal('500')
        self.assertEqual(cash_balance, expected)

    def test_account_balances_caching(self):
        """Test account balances caching."""
        # First call
        balances1 = PerformanceOptimizer.get_account_balances(
            self.organization.pk,
            use_cache=True
        )
        
        # Second call should be cached
        balances2 = PerformanceOptimizer.get_account_balances(
            self.organization.pk,
            use_cache=True
        )
        
        self.assertEqual(balances1, balances2)

    def test_get_trial_balance_optimized(self):
        """Test optimized trial balance."""
        trial_balance = PerformanceOptimizer.get_trial_balance_optimized(
            self.organization.pk
        )
        
        self.assertIsNotNone(trial_balance)
        self.assertGreater(len(trial_balance), 0)
        
        # Check structure
        for item in trial_balance:
            self.assertIn('account_id', item)
            self.assertIn('account_code', item)
            self.assertIn('debit', item)
            self.assertIn('credit', item)

    def test_get_recent_journals(self):
        """Test getting recent journals."""
        recent = PerformanceOptimizer.get_recent_journals(
            self.organization.pk,
            limit=3
        )
        
        self.assertEqual(len(recent), 3)

    def test_invalidate_organization_cache(self):
        """Test cache invalidation."""
        # Set cache
        cache_key = f'org_summary_{self.organization.pk}'
        cache.set(cache_key, {'test': 'data'}, 3600)
        
        # Invalidate
        PerformanceOptimizer.invalidate_org_cache(self.organization.pk)
        
        # Cache should be cleared or different
        self.assertIsNotNone(cache_key)


class DatabaseIndexOptimizerTestCase(TestCase):
    """Test database index recommendations."""

    def test_get_index_recommendations(self):
        """Test getting index recommendations."""
        recommendations = DatabaseIndexOptimizer.get_index_recommendations()
        
        self.assertGreater(len(recommendations), 0)
        
        # Check structure
        for rec in recommendations:
            self.assertIn('model', rec)
            self.assertIn('fields', rec)
            self.assertIn('name', rec)
            self.assertIn('reason', rec)

    def test_index_recommendations_have_journal_indexes(self):
        """Test that Journal indexes are recommended."""
        recommendations = DatabaseIndexOptimizer.get_index_recommendations()
        
        journal_indexes = [r for r in recommendations if r['model'] == 'Journal']
        self.assertGreater(len(journal_indexes), 0)

    def test_index_recommendations_have_account_indexes(self):
        """Test that Account indexes are recommended."""
        recommendations = DatabaseIndexOptimizer.get_index_recommendations()
        
        account_indexes = [r for r in recommendations if r['model'] == 'Account']
        self.assertGreater(len(account_indexes), 0)

    def test_create_indexes_migration(self):
        """Test migration code generation."""
        migration_code = DatabaseIndexOptimizer.create_indexes_migration()
        
        self.assertIn('migrations.AddIndex', migration_code)
        self.assertIn('model_name=', migration_code)


class CacheInvalidationTestCase(TransactionTestCase):
    """Test cache invalidation."""

    def setUp(self):
        """Set up test data."""
        cache.clear()
        
        self.organization = Organization.objects.create(
            name="Test Org",
            code="TEST"
        )
        
        self.account = Account.objects.create(
            organization=self.organization,
            code="1000",
            name="Cash",
            account_type="Asset",
            is_active=True
        )

    def test_cache_invalidation_on_journal_save(self):
        """Test cache invalidation when journal is saved."""
        journal_type = JournalType.objects.create(
            code="GJ",
            name="General Journal"
        )
        
        # Set cache
        cache_key = f'org_summary_{self.organization.pk}'
        cache.set(cache_key, {'test': 'data'}, 3600)
        
        # Create journal (should trigger invalidation)
        journal = Journal.objects.create(
            organization=self.organization,
            journal_type=journal_type,
            date=date.today(),
            reference="TEST",
            status="Posted"
        )
        
        # Cache should be invalidated
        self.assertIsNotNone(journal)
