from django.urls import path
from . import views

app_name = 'forms_designer'

urlpatterns = [
    path('', views.voucher_config_list, name='voucher_config_list'),
    path('history/<int:config_id>/', views.schema_history, name='schema_history'),
    path('toggle-status/<int:config_id>/', views.toggle_voucher_config_status, name='toggle_voucher_config_status'),
    path('designer/<int:config_id>/', views.designer, name='designer'),
    path('preview/<int:config_id>/', views.preview, name='preview'),
    path('designer/<int:config_id>/save/', views.save_schema_api, name='save_schema_api'),
]