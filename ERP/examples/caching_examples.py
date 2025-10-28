"""
Example Django views demonstrating advanced caching strategies
"""

from django.shortcuts import render, get_object_or_404
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView

from utils.view_caching import (
    cache_view,
    cache_view_per_user,
    cache_view_per_tenant,
    cache_api_response,
    cache_api_list,
    etag_support,
    last_modified_support,
)


# =============================================================================
# VIEW CACHING EXAMPLES
# =============================================================================

@cache_view(timeout=600, key_prefix="homepage")
def homepage(request):
    """
    Cache homepage for 10 minutes.
    All users see the same cached version.
    """
    context = {
        'title': 'Himalytix ERP',
        'features': get_features(),  # Expensive query
        'stats': get_statistics(),    # Expensive calculation
    }
    return render(request, 'home.html', context)


@cache_view_per_user(timeout=300)
def user_dashboard(request):
    """
    Cache dashboard per user for 5 minutes.
    Each user has their own cached version.
    """
    context = {
        'user': request.user,
        'journal_entries': get_user_entries(request.user),
        'notifications': get_user_notifications(request.user),
        'stats': calculate_user_stats(request.user),
    }
    return render(request, 'dashboard.html', context)


@cache_view_per_tenant(timeout=600)
def tenant_reports(request):
    """
    Cache reports per tenant for 10 minutes.
    Each tenant has their own cached version.
    """
    tenant = request.tenant  # Assumes tenant middleware
    
    context = {
        'tenant': tenant,
        'monthly_report': generate_monthly_report(tenant),
        'financial_summary': calculate_financial_summary(tenant),
    }
    return render(request, 'reports.html', context)


# =============================================================================
# DJANGO BUILT-IN CACHING
# =============================================================================

@cache_page(60 * 15)  # Cache for 15 minutes
@vary_on_headers('Accept-Language')  # Vary by language
def public_api_endpoint(request):
    """
    Use Django's built-in cache_page decorator.
    Cache varies by Accept-Language header.
    """
    data = {
        'status': 'success',
        'data': get_public_data(),
    }
    return JsonResponse(data)


# =============================================================================
# API RESPONSE CACHING
# =============================================================================

@cache_api_response(timeout=300, vary_on=['Accept-Language'])
@api_view(['GET'])
def api_get_stats(request):
    """
    Cache API response for 5 minutes.
    Different cache per language.
    """
    stats = {
        'total_entries': count_journal_entries(),
        'total_users': count_users(),
        'revenue': calculate_total_revenue(),
    }
    return Response(stats)


@cache_api_list(timeout=300, per_page=True)
@api_view(['GET'])
def api_list_entries(request):
    """
    Cache paginated list responses.
    Each page cached separately.
    """
    from journal.models import JournalEntry
    from journal.serializers import JournalEntrySerializer
    from rest_framework.pagination import PageNumberPagination
    
    paginator = PageNumberPagination()
    paginator.page_size = request.query_params.get('page_size', 50)
    
    queryset = JournalEntry.objects.all().order_by('-date')
    page = paginator.paginate_queryset(queryset, request)
    
    serializer = JournalEntrySerializer(page, many=True)
    
    return paginator.get_paginated_response(serializer.data)


# =============================================================================
# ETAG SUPPORT
# =============================================================================

@etag_support()
@api_view(['GET'])
def api_get_entry(request, entry_id):
    """
    Respond with 304 Not Modified if ETag matches.
    """
    from journal.models import JournalEntry
    from journal.serializers import JournalEntrySerializer
    
    entry = get_object_or_404(JournalEntry, id=entry_id)
    serializer = JournalEntrySerializer(entry)
    
    return Response(serializer.data)


def get_entry_last_modified(request, entry_id):
    """Helper to get last modified timestamp for entry."""
    from journal.models import JournalEntry
    
    try:
        entry = JournalEntry.objects.get(id=entry_id)
        return entry.updated_at
    except JournalEntry.DoesNotExist:
        return None


@last_modified_support(get_entry_last_modified)
@api_view(['GET'])
def api_get_entry_with_last_modified(request, entry_id):
    """
    Respond with 304 Not Modified if not modified since last request.
    """
    from journal.models import JournalEntry
    from journal.serializers import JournalEntrySerializer
    
    entry = get_object_or_404(JournalEntry, id=entry_id)
    serializer = JournalEntrySerializer(entry)
    
    return Response(serializer.data)


# =============================================================================
# CLASS-BASED VIEW WITH CACHING
# =============================================================================

class CachedAPIView(APIView):
    """
    Example class-based view with method caching.
    """
    
    @method_decorator(cache_api_response(timeout=600))
    def get(self, request):
        """Cache GET responses for 10 minutes."""
        data = {
            'message': 'This response is cached',
            'timestamp': get_current_timestamp(),
        }
        return Response(data)
    
    def post(self, request):
        """POST requests are not cached."""
        # Process data
        result = process_data(request.data)
        
        # Invalidate related cache
        from utils.view_caching import invalidate_view_cache
        invalidate_view_cache('api_get_stats')
        
        return Response({'status': 'created', 'data': result})


# =============================================================================
# CACHE INVALIDATION EXAMPLES
# =============================================================================

def create_journal_entry(request):
    """
    Create entry and invalidate related caches.
    """
    from journal.models import JournalEntry
    from utils.view_caching import invalidate_view_cache
    from django.core.cache import cache
    
    # Create entry
    entry = JournalEntry.objects.create(
        date=request.POST.get('date'),
        amount=request.POST.get('amount'),
        description=request.POST.get('description'),
    )
    
    # Invalidate caches
    invalidate_view_cache('api_list_entries')
    invalidate_view_cache('api_get_stats')
    cache.delete('dashboard:stats')
    
    # Invalidate user-specific cache
    user_id = request.user.id
    cache.delete(f'view:user:{user_id}:user_dashboard:*')
    
    return JsonResponse({'status': 'created', 'id': entry.id})


# =============================================================================
# CACHE WARMING EXAMPLES
# =============================================================================

def warm_dashboard_cache(user_id):
    """
    Pre-populate user dashboard cache.
    Called after user login or data update.
    """
    from utils.view_caching import warm_cache
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    user = User.objects.get(id=user_id)
    
    def get_dashboard_data():
        return {
            'entries': list(get_user_entries(user)),
            'notifications': list(get_user_notifications(user)),
            'stats': calculate_user_stats(user),
        }
    
    cache_key = f'dashboard:user:{user_id}'
    warm_cache(cache_key, get_dashboard_data, timeout=300)


def warm_all_caches():
    """
    Warm multiple caches on application startup.
    """
    from utils.view_caching import warm_cache_batch
    
    cache_specs = [
        {
            'key': 'homepage:stats',
            'data_func': get_statistics,
            'timeout': 600,
        },
        {
            'key': 'homepage:features',
            'data_func': get_features,
            'timeout': 3600,
        },
        {
            'key': 'api:stats',
            'data_func': lambda: {
                'total_entries': count_journal_entries(),
                'total_users': count_users(),
            },
            'timeout': 300,
        },
    ]
    
    results = warm_cache_batch(cache_specs)
    print(f"Cache warming results: {results}")


# =============================================================================
# HELPER FUNCTIONS (placeholders for examples)
# =============================================================================

def get_features():
    """Get feature list (expensive query)."""
    return ['Multi-tenant', 'Accounting', 'Reporting']


def get_statistics():
    """Calculate statistics (expensive)."""
    return {'users': 100, 'entries': 1000}


def get_user_entries(user):
    """Get user journal entries."""
    return []


def get_user_notifications(user):
    """Get user notifications."""
    return []


def calculate_user_stats(user):
    """Calculate user statistics."""
    return {}


def generate_monthly_report(tenant):
    """Generate monthly report."""
    return {}


def calculate_financial_summary(tenant):
    """Calculate financial summary."""
    return {}


def get_public_data():
    """Get public API data."""
    return {}


def count_journal_entries():
    """Count journal entries."""
    return 0


def count_users():
    """Count users."""
    return 0


def calculate_total_revenue():
    """Calculate total revenue."""
    return 0


def get_current_timestamp():
    """Get current timestamp."""
    from datetime import datetime
    return datetime.now().isoformat()


def process_data(data):
    """Process POST data."""
    return data
