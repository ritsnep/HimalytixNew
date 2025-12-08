from django.urls import path

from reporting import views

app_name = "reporting"

urlpatterns = [
    path("", views.ReportIndexView.as_view(), name="report_index"),
    path("schedules/", views.ScheduledReportListView.as_view(), name="scheduled_reports"),
    path("api/templates/", views.ReportTemplateApiView.as_view(), name="report_template_api"),
    path("api/templates/gallery/", views.ReportTemplateApiView.as_view(), name="report_template_gallery_api"),
    path("api/sample/", views.ReportSampleApiView.as_view(), name="report_sample_api"),
    path("<str:code>/designer/", views.ReportDesignerView.as_view(), name="report_designer"),
    path("<str:code>/", views.ReportDetailView.as_view(), name="report_view"),
]
