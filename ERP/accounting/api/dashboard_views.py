from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from accounting.services.dashboard_service import DashboardService


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
