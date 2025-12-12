from django.urls import path

from . import views

urlpatterns = [
    path("settings/", views.print_settings, name="print_settings"),
    path("preview/<int:journal_id>/", views.print_preview, name="print_preview"),
    path("<int:journal_id>/", views.print_page, name="print_page"),
]
