from django.urls import path
from . import views

app_name = 'metadata'

urlpatterns = [
    # Form endpoints
    path('form/<str:entity_name>/', views.get_form_html, name='get_form'),
    path('validate/<str:entity_name>/', views.validate_form, name='validate_form'),
    path('validate/<str:entity_name>/<str:field_name>/', views.validate_field, name='validate_field'),
    
    # Schema endpoints
    path('schema/<str:entity_name>/', views.get_schema, name='get_schema'),
] 