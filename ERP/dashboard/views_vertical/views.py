# dashboard/views/vertical_dashboard_views.py
"""
Vertical Dashboard Views

Provides dashboard endpoints for each industry vertical:
- Distributors: DIFOT, Fill Rate, Inventory Turnover
- Retailers: GMROI, Sell-Through, Top Products
- Manufacturers: OEE, Yield, Production Variance
- SaaS: MRR/ARR, Churn, LTV:CAC
"""
from datetime import date, timedelta
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils.dateparse import parse_date

from dashboard.utils.vertical_metrics import (
    DistributorMetrics,
    RetailerMetrics,
    ManufacturerMetrics,
    SaaSMetrics,
    ServiceMetrics
)


# ============================================================================
# DISTRIBUTOR DASHBOARDS
# ============================================================================

@login_required
@require_http_methods(["GET"])
def distributor_dashboard(request):
    """
    Distributor KPI Dashboard
    
    Query Parameters:
        - start_date: YYYY-MM-DD (default: 30 days ago)
        - end_date: YYYY-MM-DD (default: today)
        - warehouse_id: Optional warehouse filter
    
    Returns:
        {
            'difot': {...},
            'inventory_turnover': {...},
            'order_fill_rate': {...}
        }
    """
    organization = request.user.organization
    
    # Parse date range
    end_date = parse_date(request.GET.get('end_date')) or date.today()
    start_date = parse_date(request.GET.get('start_date')) or (end_date - timedelta(days=30))
    warehouse_id = request.GET.get('warehouse_id')
    
    metrics = DistributorMetrics(organization)
    
    # Calculate KPIs
    difot = metrics.calculate_difot(
        start_date=start_date,
        end_date=end_date,
        warehouse_id=int(warehouse_id) if warehouse_id else None
    )
    
    turnover = metrics.calculate_inventory_turnover(
        start_date=start_date,
        end_date=end_date
    )
    
    fill_rate = metrics.calculate_order_fill_rate(
        start_date=start_date,
        end_date=end_date
    )
    
    return JsonResponse({
        'date_range': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        },
        'difot': difot,
        'inventory_turnover': turnover,
        'order_fill_rate': fill_rate
    })


@login_required
@require_http_methods(["GET"])
def distributor_difot_trend(request):
    """
    DIFOT Trend over Time (weekly breakdown)
    
    Returns weekly DIFOT percentages for the last 12 weeks
    """
    organization = request.user.organization
    metrics = DistributorMetrics(organization)
    
    end_date = date.today()
    trend_data = []
    
    # Get 12 weeks of data
    for week in range(12):
        week_end = end_date - timedelta(days=week * 7)
        week_start = week_end - timedelta(days=6)
        
        difot = metrics.calculate_difot(
            start_date=week_start,
            end_date=week_end
        )
        
        trend_data.insert(0, {
            'week': week_start.isoformat(),
            'difot_percentage': difot['difot_percentage'],
            'total_orders': difot['total_orders']
        })
    
    return JsonResponse({
        'trend': trend_data
    })


# ============================================================================
# RETAILER DASHBOARDS
# ============================================================================

@login_required
@require_http_methods(["GET"])
def retailer_dashboard(request):
    """
    Retailer KPI Dashboard
    
    Query Parameters:
        - start_date: YYYY-MM-DD (default: 30 days ago)
        - end_date: YYYY-MM-DD (default: today)
        - category_id: Optional category filter
    
    Returns:
        {
            'gmroi': {...},
            'sell_through': {...},
            'top_products': [...]
        }
    """
    organization = request.user.organization
    
    # Parse parameters
    end_date = parse_date(request.GET.get('end_date')) or date.today()
    start_date = parse_date(request.GET.get('start_date')) or (end_date - timedelta(days=30))
    category_id = request.GET.get('category_id')
    
    metrics = RetailerMetrics(organization)
    
    # Calculate KPIs
    gmroi = metrics.calculate_gmroi(
        start_date=start_date,
        end_date=end_date,
        category_id=int(category_id) if category_id else None
    )
    
    sell_through = metrics.calculate_sell_through_rate(
        start_date=start_date,
        end_date=end_date,
        category_id=int(category_id) if category_id else None
    )
    
    top_products = metrics.get_top_selling_products(
        start_date=start_date,
        end_date=end_date,
        limit=10
    )
    
    return JsonResponse({
        'date_range': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        },
        'gmroi': gmroi,
        'sell_through': sell_through,
        'top_products': top_products
    })


@login_required
@require_http_methods(["GET"])
def retailer_category_performance(request):
    """
    Category Performance Comparison
    
    Returns GMROI and sell-through for all categories
    """
    from inventory.models import ProductCategory
    
    organization = request.user.organization
    metrics = RetailerMetrics(organization)
    
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    
    categories = ProductCategory.objects.filter(organization=organization)
    
    category_data = []
    for category in categories:
        gmroi = metrics.calculate_gmroi(
            start_date=start_date,
            end_date=end_date,
            category_id=category.id
        )
        
        sell_through = metrics.calculate_sell_through_rate(
            start_date=start_date,
            end_date=end_date,
            category_id=category.id
        )
        
        category_data.append({
            'category_id': category.id,
            'category_name': category.name,
            'gmroi': gmroi['gmroi'],
            'sell_through_percentage': sell_through['sell_through_percentage']
        })
    
    return JsonResponse({
        'categories': category_data
    })


# ============================================================================
# MANUFACTURER DASHBOARDS
# ============================================================================

@login_required
@require_http_methods(["GET"])
def manufacturer_dashboard(request):
    """
    Manufacturer KPI Dashboard
    
    Query Parameters:
        - start_date: YYYY-MM-DD (default: 30 days ago)
        - end_date: YYYY-MM-DD (default: today)
        - work_center_id: Optional work center filter
    
    Returns:
        {
            'oee': {...},
            'yield': {...},
            'cost_variance': {...}
        }
    """
    organization = request.user.organization
    
    # Parse parameters
    end_date = parse_date(request.GET.get('end_date')) or date.today()
    start_date = parse_date(request.GET.get('start_date')) or (end_date - timedelta(days=30))
    work_center_id = request.GET.get('work_center_id')
    
    metrics = ManufacturerMetrics(organization)
    
    # Calculate KPIs
    oee = metrics.calculate_oee(
        start_date=start_date,
        end_date=end_date,
        work_center_id=int(work_center_id) if work_center_id else None
    )
    
    yield_rate = metrics.calculate_yield_rate(
        start_date=start_date,
        end_date=end_date
    )
    
    cost_variance = metrics.calculate_production_variance(
        start_date=start_date,
        end_date=end_date
    )
    
    return JsonResponse({
        'date_range': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        },
        'oee': oee,
        'yield': yield_rate,
        'cost_variance': cost_variance
    })


@login_required
@require_http_methods(["GET"])
def manufacturer_oee_trend(request):
    """
    OEE Trend over Time (daily breakdown for last 30 days)
    """
    organization = request.user.organization
    metrics = ManufacturerMetrics(organization)
    
    end_date = date.today()
    trend_data = []
    
    # Get 30 days of data
    for day in range(30):
        current_date = end_date - timedelta(days=day)
        
        oee = metrics.calculate_oee(
            start_date=current_date,
            end_date=current_date
        )
        
        trend_data.insert(0, {
            'date': current_date.isoformat(),
            'oee_percentage': oee['oee_percentage'],
            'availability': oee['availability'],
            'performance': oee['performance'],
            'quality': oee['quality']
        })
    
    return JsonResponse({
        'trend': trend_data
    })


# ============================================================================
# SAAS DASHBOARDS
# ============================================================================

@login_required
@require_http_methods(["GET"])
def saas_dashboard(request):
    """
    SaaS KPI Dashboard
    
    Query Parameters:
        - start_date: YYYY-MM-DD (default: 30 days ago)
        - end_date: YYYY-MM-DD (default: today)
    
    Returns:
        {
            'mrr_arr': {...},
            'churn': {...},
            'ltv_cac': {...}
        }
    """
    organization = request.user.organization
    
    # Parse parameters
    end_date = parse_date(request.GET.get('end_date')) or date.today()
    start_date = parse_date(request.GET.get('start_date')) or (end_date - timedelta(days=30))
    
    metrics = SaaSMetrics(organization)
    
    # Calculate KPIs
    mrr_arr = metrics.calculate_mrr_arr(as_of_date=end_date)
    churn = metrics.calculate_churn_rate(start_date=start_date, end_date=end_date)
    ltv_cac = metrics.calculate_ltv_cac(start_date=start_date, end_date=end_date)
    
    return JsonResponse({
        'date_range': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        },
        'mrr_arr': mrr_arr,
        'churn': churn,
        'ltv_cac': ltv_cac
    })


@login_required
@require_http_methods(["GET"])
def saas_mrr_trend(request):
    """
    MRR Trend over Time (monthly for last 12 months)
    """
    organization = request.user.organization
    metrics = SaaSMetrics(organization)
    
    end_date = date.today()
    trend_data = []
    
    # Get 12 months of data
    for month in range(12):
        # Calculate first day of each month
        target_date = end_date.replace(day=1) - timedelta(days=month * 30)
        target_date = target_date.replace(day=1)
        
        mrr_arr = metrics.calculate_mrr_arr(as_of_date=target_date)
        
        trend_data.insert(0, {
            'month': target_date.isoformat(),
            'mrr': mrr_arr['mrr'],
            'total_subscriptions': mrr_arr['total_subscriptions'],
            'arpu': mrr_arr['arpu']
        })
    
    return JsonResponse({
        'trend': trend_data
    })


@login_required
@require_http_methods(["GET"])
def saas_cohort_analysis(request):
    """
    Subscription Cohort Analysis
    
    Query Parameters:
        - cohort_month: YYYY-MM-DD (default: 6 months ago)
    
    Returns retention rates for a specific cohort
    """
    organization = request.user.organization
    metrics = SaaSMetrics(organization)
    
    # Parse cohort month
    cohort_date = parse_date(request.GET.get('cohort_month'))
    if not cohort_date:
        cohort_date = date.today() - timedelta(days=180)
    
    cohort_date = cohort_date.replace(day=1)  # First day of month
    
    cohort_data = metrics.get_subscription_cohort_analysis(cohort_month=cohort_date)
    
    return JsonResponse(cohort_data)


# ============================================================================
# SERVICE DASHBOARDS
# ============================================================================

@login_required
@require_http_methods(["GET"])
def service_dashboard(request):
    """
    Service Management KPI Dashboard
    
    Query Parameters:
        - start_date: YYYY-MM-DD (default: 30 days ago)
        - end_date: YYYY-MM-DD (default: today)
    
    Returns:
        {
            'sla_compliance': {...},
            'mttr': {...}
        }
    """
    organization = request.user.organization
    
    # Parse parameters
    end_date = parse_date(request.GET.get('end_date')) or date.today()
    start_date = parse_date(request.GET.get('start_date')) or (end_date - timedelta(days=30))
    
    metrics = ServiceMetrics(organization)
    
    # Calculate KPIs
    sla = metrics.calculate_sla_compliance(
        start_date=start_date,
        end_date=end_date
    )
    
    mttr = metrics.calculate_mttr(
        start_date=start_date,
        end_date=end_date
    )
    
    return JsonResponse({
        'date_range': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        },
        'sla_compliance': sla,
        'mttr': mttr
    })


# ============================================================================
# UNIFIED DASHBOARD (All Verticals)
# ============================================================================

@login_required
@require_http_methods(["GET"])
def unified_dashboard(request):
    """
    Unified Dashboard showing KPIs across all verticals
    
    Query Parameters:
        - start_date: YYYY-MM-DD (default: 30 days ago)
        - end_date: YYYY-MM-DD (default: today)
    
    Returns all vertical metrics in a single response
    """
    organization = request.user.organization
    
    # Parse parameters
    end_date = parse_date(request.GET.get('end_date')) or date.today()
    start_date = parse_date(request.GET.get('start_date')) or (end_date - timedelta(days=30))
    
    # Initialize all metric calculators
    distributor = DistributorMetrics(organization)
    retailer = RetailerMetrics(organization)
    manufacturer = ManufacturerMetrics(organization)
    saas = SaaSMetrics(organization)
    service = ServiceMetrics(organization)
    
    # Collect all metrics
    data = {
        'date_range': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        },
        'distributor': {
            'difot': distributor.calculate_difot(start_date, end_date),
            'inventory_turnover': distributor.calculate_inventory_turnover(start_date, end_date),
            'order_fill_rate': distributor.calculate_order_fill_rate(start_date, end_date)
        },
        'retailer': {
            'gmroi': retailer.calculate_gmroi(start_date, end_date),
            'sell_through': retailer.calculate_sell_through_rate(start_date, end_date),
            'top_products': retailer.get_top_selling_products(start_date, end_date, limit=5)
        },
        'manufacturer': {
            'oee': manufacturer.calculate_oee(start_date, end_date),
            'yield': manufacturer.calculate_yield_rate(start_date, end_date),
            'cost_variance': manufacturer.calculate_production_variance(start_date, end_date)
        },
        'saas': {
            'mrr_arr': saas.calculate_mrr_arr(as_of_date=end_date),
            'churn': saas.calculate_churn_rate(start_date, end_date),
            'ltv_cac': saas.calculate_ltv_cac(start_date, end_date)
        },
        'service': {
            'sla_compliance': service.calculate_sla_compliance(start_date, end_date),
            'mttr': service.calculate_mttr(start_date, end_date)
        }
    }
    
    return JsonResponse(data)
