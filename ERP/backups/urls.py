from django.urls import path
from . import views

app_name = 'backups'

urlpatterns = [
    path('dashboard/', views.export_dashboard, name='dashboard'),
    path('download/<str:dataset>/<str:fmt>/', views.ExportView.as_view(), name='download'),
    path('trigger/', views.trigger_backup, name='trigger'),
    path('get-backup/<uuid:job_id>/', views.download_backup, name='get_backup'),
    path('delete-backup/<uuid:job_id>/', views.delete_backup, name='delete_backup'),
    path('list-partial/', views.backup_list_partial, name='list_partial'),
]
