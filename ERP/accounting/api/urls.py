"""
REST API URLs - Phase 3 Task 7

API Endpoints:
- /api/v1/accounts/ - Account CRUD
- /api/v1/journals/ - Journal CRUD
- /api/v1/approval-logs/ - Approval logs
- /api/v1/periods/ - Accounting periods
- /api/v1/trial-balance/ - Trial balance report
- /api/v1/general-ledger/ - General ledger
- /api/v1/import/ - Import journals
- /api/v1/export/ - Export journals
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from accounting.api.serializers import (
    AccountViewSet,
    JournalViewSet,
    ApprovalLogViewSet,
    AccountingPeriodViewSet,
    trial_balance_api,
    general_ledger_api,
    import_journals_api,
    export_journals_api
)

# Create router for viewsets
router = DefaultRouter()
router.register(r'accounts', AccountViewSet, basename='api-account')
router.register(r'journals', JournalViewSet, basename='api-journal')
router.register(r'approval-logs', ApprovalLogViewSet, basename='api-approval-log')
router.register(r'periods', AccountingPeriodViewSet, basename='api-period')

app_name = 'api'

urlpatterns = [
    # ViewSets via router
    path('', include(router.urls)),
    
    # Report endpoints
    path('trial-balance/', trial_balance_api, name='api-trial-balance'),
    path('general-ledger/', general_ledger_api, name='api-general-ledger'),
    
    # Import/Export endpoints
    path('import/', import_journals_api, name='api-import'),
    path('export/', export_journals_api, name='api-export'),
    
    # API authentication
    path('auth/', include('rest_framework.urls')),
]
