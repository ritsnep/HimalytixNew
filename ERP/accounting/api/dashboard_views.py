from datetime import datetime

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from accounting.services.dashboard_service import DashboardService
from accounting.services.tax_liability_service import TaxLiabilityService


def _resolve_period_start(value):
    if not value:
        return timezone.now().date().replace(day=1)
    try:
        parsed = datetime.strptime(value, "%Y-%m")
    except ValueError as exc:
        raise ValueError("Invalid period format. Use YYYY-MM.") from exc
    return parsed.date().replace(day=1)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_metrics(request):
    organization = request.user.get_active_organization()
    if not organization:
        return Response({'detail': 'Active organization required.'}, status=400)
    service = DashboardService(organization)
    return Response(service.get_dashboard_metrics())


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_export_csv(request):
    organization = request.user.get_active_organization()
    if not organization:
        return Response({'detail': 'Active organization required.'}, status=400)
    service = DashboardService(organization)
    csv_data = service.export_csv()
    return Response({'csv': csv_data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def vat_summary(request):
    organization = request.user.get_active_organization()
    if not organization:
        return Response({'detail': 'Active organization required.'}, status=400)
    try:
        period_start = _resolve_period_start(request.query_params.get('period'))
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=400)
    service = TaxLiabilityService(organization)
    return Response(service.build_vat_summary(period_start))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def nfrs_schedule(request):
    organization = request.user.get_active_organization()
    if not organization:
        return Response({'detail': 'Active organization required.'}, status=400)
    try:
        period_start = _resolve_period_start(request.query_params.get('period'))
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=400)
    service = TaxLiabilityService(organization)
    return Response(service.build_nfrs_schedule(period_start))
