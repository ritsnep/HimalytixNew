from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import NocPurchase, LogisticsTrip


def dashboard(request):
    """
    Simple dashboard view that renders the static HTML + JS dashboard template.
    Later you can:
      - Replace inline JS demo data with real API calls.
      - Or pass aggregates in `context` for server-side rendering.
    """
    return render(request, "lpg_vertical/dashboard.html")


@require_GET
def api_dashboard_summary(request):
    """
    Example JSON endpoint for dashboard KPIs.

    For now returns static/sample numbers.
    Replace with real aggregations from your accounting/inventory modules.
    """
    data = {
        "revenue": 6452300,
        "cylinders_sold": 32456,
        "empty_collected": 28901,
        "pending_deliveries": 123,
    }
    return JsonResponse(data)


@require_GET
def api_recent_noc_purchases(request):
    """
    Example endpoint to feed the 'Recent NOC Purchases' table.

    Currently pulls the last 10 NocPurchase rows.
    """
    purchases = NocPurchase.objects.order_by("-purchase_date")[:10]
    data = [
        {
            "date": p.purchase_date.isoformat(),
            "bill_no": p.bill_no,
            "quantity_mt": str(p.quantity_mt),
            "total_amount": str(p.total_amount),
        }
        for p in purchases
    ]
    return JsonResponse({"results": data})


@require_GET
def api_recent_logistics(request):
    """
    Example endpoint to feed 'Recent Logistics' table.
    """
    trips = LogisticsTrip.objects.order_by("-trip_date")[:10]
    data = [
        {
            "date": t.trip_date.isoformat(),
            "provider": t.transport_provider_name,
            "vehicle": t.vehicle_number,
            "cylinders": t.cylinder_count,
            "cost": str(t.cost),
        }
        for t in trips
    ]
    return JsonResponse({"results": data})
