from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.db import connection
from usermanagement.models import Permission, UserRole, UserPermission
from usermanagement.utils import PermissionUtils
import time
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Monitor permission system performance and generate metrics'

    def add_arguments(self, parser):
        parser.add_argument(
            '--iterations',
            type=int,
            default=100,
            help='Number of permission checks to perform for benchmarking'
        )
        parser.add_argument(
            '--users',
            type=int,
            default=10,
            help='Number of users to simulate'
        )
        parser.add_argument(
            '--cache-analysis',
            action='store_true',
            help='Analyze cache performance'
        )

    def handle(self, *args, **options):
        self.stdout.write('=== Permission System Performance Monitor ===\n')

        iterations = options['iterations']
        user_count = options['users']

        # Basic metrics
        self.show_basic_metrics()

        # Cache analysis
        if options['cache_analysis']:
            self.analyze_cache_performance()

        # Performance benchmarking
        self.benchmark_permission_checks(iterations, user_count)

        # Query optimization analysis
        self.analyze_query_performance()

    def show_basic_metrics(self):
        """Show basic permission system metrics."""
        self.stdout.write('📊 Basic Metrics:')
        self.stdout.write(f'   Total Permissions: {Permission.objects.count()}')
        self.stdout.write(f'   Total User Roles: {UserRole.objects.count()}')
        self.stdout.write(f'   Total User Permissions: {UserPermission.objects.count()}')

        # Cache info
        cache_stats = self.get_cache_stats()
        self.stdout.write(f'   Cache Keys: {cache_stats.get("keys", "N/A")}')
        self.stdout.write(f'   Cache Hit Rate: {cache_stats.get("hit_rate", "N/A")}%')
        self.stdout.write('')

    def get_cache_stats(self):
        """Get cache statistics if using Redis."""
        try:
            # Try to get Redis stats if available
            from django_redis import get_redis_connection
            redis_conn = get_redis_connection("default")

            info = redis_conn.info()
            keys = redis_conn.dbsize()

            # Estimate hit rate (simplified)
            hits = info.get('keyspace_hits', 0)
            misses = info.get('keyspace_misses', 0)
            total = hits + misses
            hit_rate = (hits / total * 100) if total > 0 else 0

            return {
                'keys': keys,
                'hit_rate': round(hit_rate, 2),
                'hits': hits,
                'misses': misses
            }
        except ImportError:
            return {'keys': 'N/A (not using Redis)', 'hit_rate': 'N/A'}
        except Exception as e:
            return {'keys': f'Error: {e}', 'hit_rate': 'N/A'}

    def analyze_cache_performance(self):
        """Analyze cache performance."""
        self.stdout.write('🔍 Cache Performance Analysis:')

        # Test cache operations
        test_key = 'performance_test_key'
        test_value = {'test': 'data', 'timestamp': time.time()}

        # Write test
        start_time = time.time()
        cache.set(test_key, test_value, 60)
        write_time = (time.time() - start_time) * 1000

        # Read test
        start_time = time.time()
        result = cache.get(test_key)
        read_time = (time.time() - start_time) * 1000

        # Delete test
        cache.delete(test_key)

        self.stdout.write(f'   Cache Write Time: {write_time:.2f}ms')
        self.stdout.write(f'   Cache Read Time: {read_time:.2f}ms')
        self.stdout.write(f'   Cache Data Integrity: {"✓" if result == test_value else "✗"}')
        self.stdout.write('')

    def benchmark_permission_checks(self, iterations, user_count):
        """Benchmark permission checking performance."""
        self.stdout.write(f'⚡ Permission Check Benchmark ({iterations} iterations, {user_count} users):')

        from usermanagement.models import CustomUser, Organization

        # Get sample users and organization
        users = list(CustomUser.objects.filter(is_active=True)[:user_count])
        org = Organization.objects.first()

        if not users or not org:
            self.stdout.write('   Skipping benchmark: No active users or organizations found')
            return

        total_time = 0
        checks_performed = 0

        for i in range(iterations):
            user = users[i % len(users)]

            start_time = time.time()
            result = PermissionUtils.has_permission(user, org, 'accounting', 'invoice', 'view')
            elapsed = time.time() - start_time

            total_time += elapsed
            checks_performed += 1

        avg_time = (total_time / checks_performed) * 1000 if checks_performed > 0 else 0

        self.stdout.write(f'   Total Checks: {checks_performed}')
        self.stdout.write(f'   Total Time: {total_time:.4f}s')
        self.stdout.write(f'   Average Time: {avg_time:.2f}ms per check')
        self.stdout.write(f'   Checks/Second: {checks_performed / total_time:.1f}' if total_time > 0 else '   Checks/Second: N/A')
        self.stdout.write('')

    def analyze_query_performance(self):
        """Analyze database query performance."""
        self.stdout.write('🗄️  Query Performance Analysis:')

        queries_executed = len(connection.queries)
        initial_queries = queries_executed

        # Test a typical permission lookup
        from usermanagement.models import CustomUser, Organization
        user = CustomUser.objects.filter(is_active=True).first()
        org = Organization.objects.first()

        if user and org:
            # Clear query log
            connection.queries_log.clear()

            # Perform permission check
            PermissionUtils.get_user_permissions(user, org)

            queries_used = len(connection.queries)
            self.stdout.write(f'   Queries for permission lookup: {queries_used}')

            # Analyze query types
            select_count = sum(1 for q in connection.queries if q['sql'].strip().upper().startswith('SELECT'))
            self.stdout.write(f'   SELECT queries: {select_count}')

            # Check for N+1 query patterns
            if queries_used > 3:  # More than expected for optimized lookup
                self.stdout.write('   ⚠️  Potential N+1 query issue detected')
            else:
                self.stdout.write('   ✓ Query count looks optimized')
        else:
            self.stdout.write('   Skipping query analysis: No test data available')

        self.stdout.write('')

    def show_recommendations(self):
        """Show performance recommendations."""
        self.stdout.write('💡 Performance Recommendations:')

        cache_stats = self.get_cache_stats()
        hit_rate = cache_stats.get('hit_rate', 0)

        if isinstance(hit_rate, (int, float)) and hit_rate < 80:
            self.stdout.write('   • Cache hit rate is low. Consider increasing cache timeout or optimizing cache keys')

        # Check for missing indexes
        from django.db import connection
        with connection.cursor() as cursor:
            # Check if permission-related indexes exist
            cursor.execute("""
                SELECT indexname FROM pg_indexes
                WHERE tablename IN ('usermanagement_permission', 'usermanagement_userrole', 'usermanagement_userpermission')
                AND indexname LIKE '%codename%' OR indexname LIKE '%user_id%' OR indexname LIKE '%organization_id%'
            """)
            indexes = cursor.fetchall()

        if len(indexes) < 6:  # Expecting several key indexes
            self.stdout.write('   • Consider adding database indexes on frequently queried fields')
            self.stdout.write('     - usermanagement_permission.codename')
            self.stdout.write('     - usermanagement_userrole.user_id, organization_id')
            self.stdout.write('     - usermanagement_userpermission.user_id, organization_id')

        self.stdout.write('   • Use bulk operations for multiple permission checks')
        self.stdout.write('   • Consider implementing permission result caching at view level')
        self.stdout.write('')