from django.urls import path

from . import views

app_name = "notification_center"

urlpatterns = [
    path("notifications/", views.notification_list, name="list"),
    path("notifications/mark-read/<int:pk>/", views.notification_mark_read, name="mark_read"),
    path("notifications/mark-all-read/", views.notification_mark_all_read, name="mark_all_read"),
    path("approvals/<int:pk>/", views.approval_detail, name="approval_detail"),
    path("approvals/<int:pk>/decision/", views.approval_decision, name="approval_decision"),
]
