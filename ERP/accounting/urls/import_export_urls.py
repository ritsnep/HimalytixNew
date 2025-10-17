"""
URL Configuration for Batch Import/Export - Phase 3 Task 3

Routes:
- /import-export/ → List imports/exports with history
- /import-create/ → Create new import
- /download-import-template/ → Download Excel template
- /export/ → Export journals
- /import-status/<id>/ → Check import status
- /bulk-action/ → Perform bulk operations
"""

from django.urls import path
from accounting.views.import_export_views import (
    ImportListView,
    ImportCreateView,
    DownloadTemplateView,
    ExportView,
    ImportStatusView,
    BulkActionView
)

app_name = "import_export"

urlpatterns = [
    # Main import/export page with history
    path('import-export/', 
         ImportListView.as_view(), 
         name='list'),
    
    # File upload and processing
    path('import-create/', 
         ImportCreateView.as_view(), 
         name='create'),
    
    # Download template
    path('download-import-template/', 
         DownloadTemplateView.as_view(), 
         name='download_template'),
    
    # Export journals
    path('export/', 
         ExportView.as_view(), 
         name='export'),
    
    # Check import progress
    path('import-status/<int:id>/', 
         ImportStatusView.as_view(), 
         name='status'),
    
    # Bulk operations (post, delete, validate)
    path('bulk-action/', 
         BulkActionView.as_view(), 
         name='bulk_action'),
]
