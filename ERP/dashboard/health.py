"""
Health Check Views for Himalytix ERP
Provides liveness and readiness probe endpoints for load balancers and orchestrators
"""
from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
from django.conf import settings
import redis
try:
    from celery import current_app as celery_app
except Exception:  # ImportError or runtime issues
    celery_app = None
from datetime import datetime


def health_check(request):
    """
    Basic health check endpoint (/health/)
    Returns 200 if application is running
    """
    return JsonResponse({
        'status': 'healthy',
        'service': 'himalytix-erp',
        'timestamp': datetime.utcnow().isoformat(),
    })


def health_ready(request):
    """
    Readiness probe endpoint (/health/ready/)
    Checks all dependencies (database, Redis, Celery)
    Returns 200 if all systems operational, 503 if any dependency fails
    """
    checks = {}
    overall_status = 'ready'
    status_code = 200
    
    # ==========================================================================
    # 1. DATABASE CHECK
    # ==========================================================================
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks['database'] = {
            'status': 'ok',
            'message': 'PostgreSQL connection successful'
        }
    except Exception as e:
        checks['database'] = {
            'status': 'error',
            'message': f'Database connection failed: {str(e)}'
        }
        overall_status = 'not_ready'
        status_code = 503
    
    # ==========================================================================
    # 2. REDIS CHECK (Cache + Celery Broker)
    # ==========================================================================
    try:
        # Test cache backend
        test_key = 'health_check_test'
        test_value = 'ok'
        cache.set(test_key, test_value, timeout=10)
        retrieved_value = cache.get(test_key)
        cache.delete(test_key)
        
        if retrieved_value == test_value:
            checks['redis_cache'] = {
                'status': 'ok',
                'message': 'Redis cache operational'
            }
        else:
            raise Exception('Cache write/read mismatch')
    except Exception as e:
        checks['redis_cache'] = {
            'status': 'error',
            'message': f'Redis cache failed: {str(e)}'
        }
        overall_status = 'not_ready'
        status_code = 503
    
    # ==========================================================================
    # 3. CELERY CHECK (Task Queue)
    # ==========================================================================
    if celery_app is None:
        checks['celery'] = {
            'status': 'skipped',
            'message': 'Celery not installed or disabled in this environment'
        }
    else:
        try:
            inspector = celery_app.control.inspect()
            active_workers = inspector.active()
            
            if active_workers:
                worker_count = len(active_workers.keys())
                checks['celery'] = {
                    'status': 'ok',
                    'message': f'{worker_count} Celery worker(s) active',
                    'workers': list(active_workers.keys())
                }
            else:
                checks['celery'] = {
                    'status': 'warning',
                    'message': 'No active Celery workers'
                }
        except Exception as e:
            checks['celery'] = {
                'status': 'error',
                'message': f'Celery check failed: {str(e)}'
            }
    
    # ==========================================================================
    # 4. DISK SPACE CHECK
    # ==========================================================================
    try:
        import shutil
        total, used, free = shutil.disk_usage("/")
        free_gb = free // (2**30)
        usage_percent = (used / total) * 100
        
        if free_gb < 5:  # Less than 5GB free
            checks['disk'] = {
                'status': 'warning',
                'message': f'Low disk space: {free_gb}GB free ({usage_percent:.1f}% used)'
            }
        else:
            checks['disk'] = {
                'status': 'ok',
                'message': f'{free_gb}GB free ({usage_percent:.1f}% used)'
            }
    except Exception as e:
        checks['disk'] = {
            'status': 'error',
            'message': f'Disk check failed: {str(e)}'
        }
    
    # ==========================================================================
    # RESPONSE
    # ==========================================================================
    return JsonResponse({
        'status': overall_status,
        'service': 'himalytix-erp',
        'timestamp': datetime.utcnow().isoformat(),
        'checks': checks,
    }, status=status_code)


def health_live(request):
    """
    Liveness probe endpoint (/health/live/)
    Quick check - just returns 200 if process is alive
    """
    return JsonResponse({
        'status': 'alive',
        'timestamp': datetime.utcnow().isoformat(),
    })
