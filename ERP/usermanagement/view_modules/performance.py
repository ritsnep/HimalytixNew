from django.shortcuts import render
from django.contrib.auth.decorators import user_passes_test
from django.http import JsonResponse
from django.core.cache import cache
from django.db import connection
from usermanagement.models import Permission, UserRole, UserPermission, CustomUser, Organization
from usermanagement.utils import PermissionUtils
from utils.logging_utils import StructuredLogger
import time
import json
from collections import defaultdict

logger = StructuredLogger('performance_monitor')

@user_passes_test(lambda u: u.is_superuser or getattr(u, 'role', None) == 'superadmin')
def permission_performance_dashboard(request):
    """Performance monitoring dashboard for permission system."""

    # Get basic metrics
    metrics = get_basic_metrics()

    # Get cache statistics
    cache_stats = get_cache_statistics()

    # Get recent permission checks (last 10)
    recent_checks = get_recent_permission_checks()

    # Get slow queries (queries taking >10ms in last hour)
    slow_queries = get_slow_queries()

    context = {
        'metrics': metrics,
        'cache_stats': cache_stats,
        'recent_checks': recent_checks,
        'slow_queries': slow_queries,
        'benchmark_results': run_permission_benchmark(),
    }

    return render(request, 'usermanagement/permission_performance.html', context)

@user_passes_test(lambda u: u.is_superuser or getattr(u, 'role', None) == 'superadmin')
def permission_metrics_api(request):
    """API endpoint for real-time permission metrics."""

    metrics = get_basic_metrics()
    cache_stats = get_cache_statistics()

    return JsonResponse({
        'timestamp': int(time.time()),
        'metrics': metrics,
        'cache': cache_stats,
        'benchmarks': run_permission_benchmark(),
        'health_status': 'healthy' if cache_stats.get('hit_rate', 0) > 80 else 'warning'
    })

def get_basic_metrics():
    """Get basic permission system metrics."""
    return {
        'total_permissions': Permission.objects.count(),
        'total_user_roles': UserRole.objects.count(),
        'total_user_permissions': UserPermission.objects.count(),
        'active_users': CustomUser.objects.filter(is_active=True).count(),
        'total_organizations': Organization.objects.count(),
    }

def get_cache_statistics():
    """Get cache performance statistics."""
    try:
        # Get cache info from django-redis if available
        cache_info = cache.get('__cache_info__', {})
        return {
            'backend': 'redis',
            'keys': cache_info.get('keys', 0),
            'hit_rate': cache_info.get('hit_rate', 0),
            'hits': cache_info.get('hits', 0),
            'misses': cache_info.get('misses', 0),
            'memory_usage': cache_info.get('memory_usage', 'unknown'),
        }
    except:
        return {
            'backend': 'unknown',
            'keys': 0,
            'hit_rate': 0,
            'hits': 0,
            'misses': 0,
            'memory_usage': 'unknown',
        }

def get_recent_permission_checks():
    """Get recent permission check logs."""
    # This would require logging permission checks
    # For now, return mock data
    return [
        {'timestamp': time.time() - i*60, 'user': f'user_{i}', 'permission': f'perm_{i}', 'result': True, 'duration_ms': 2.5 + i*0.1}
        for i in range(10)
    ]

def get_slow_queries():
    """Get slow database queries from recent activity."""
    # This would require query logging
    # For now, return mock data
    return [
        {'query': f'SELECT * FROM {table}', 'duration_ms': 50 + i*10, 'timestamp': time.time() - i*300}
        for i, table in enumerate(['permissions', 'user_roles', 'organizations'])
    ]

def run_permission_benchmark():
    """Run a quick permission checking benchmark."""
    users = list(CustomUser.objects.filter(is_active=True)[:10])
    permissions = ['accounting_invoice_view', 'inventory_item_create', 'user_management']

    total_checks = 0
    total_time = 0

    for user in users:
        for perm in permissions:
            start_time = time.time()
            result = PermissionUtils.has_codename(user, user.organization if hasattr(user, 'organization') else None, perm)
            duration = time.time() - start_time
            total_time += duration
            total_checks += 1

    return {
        'total_checks': total_checks,
        'total_time_ms': total_time * 1000,
        'average_time_ms': (total_time * 1000) / total_checks if total_checks > 0 else 0,
        'checks_per_second': total_checks / total_time if total_time > 0 else 0,
    }
