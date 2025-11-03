from django.urls import path
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .api_views import VoucherUDFConfigViewSet, VoucherSchemaViewSet, SchemaTemplateViewSet

app_name = 'forms_designer'

# API Router
router = DefaultRouter()
router.register(r'udfs', VoucherUDFConfigViewSet, basename='udf')
router.register(r'schemas', VoucherSchemaViewSet, basename='schema')
router.register(r'templates', SchemaTemplateViewSet, basename='template')

urlpatterns = [
    # Main views
    path('', views.voucher_config_list, name='voucher_config_list'),
    path('history/<int:config_id>/', views.schema_history, name='schema_history'),
    path('toggle-status/<int:config_id>/', views.toggle_voucher_config_status, name='toggle_voucher_config_status'),
    
    # Designer views
    path('designer/<int:config_id>/', views.designer, name='designer'),
    path('designer/<int:config_id>/v2/', views.designer_v2, name='designer_v2'),  # New enhanced designer
    path('preview/<int:config_id>/', views.preview, name='preview'),
    path('designer/<int:config_id>/save/', views.save_schema_api, name='save_schema_api'),
    
    # API routes
    path('api/', include(router.urls)),
]