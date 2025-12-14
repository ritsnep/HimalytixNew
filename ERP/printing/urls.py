from django.urls import path

from . import views

urlpatterns = [
    path("settings/", views.print_settings, name="print_settings"),
    path("templates/", views.template_list, name="template_list"),
    path("templates/create/", views.template_create, name="template_create"),
    path("templates/<int:pk>/edit/", views.template_update, name="template_update"),
    path("templates/<int:pk>/delete/", views.template_delete, name="template_delete"),
    path("preview/<str:document_type>/<int:doc_id>/", views.print_preview, name="print_preview"),
    path("<str:document_type>/<int:doc_id>/", views.print_page, name="print_page"),
]
