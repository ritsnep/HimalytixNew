from django.urls import path
from . import views

urlpatterns = [
    # JSON APIs
    path("api/locations/children", views.api_location_children, name="api_location_children"),
    path("api/locations/search", views.api_location_search, name="api_location_search"),
    path("api/clusters", views.api_clusters, name="api_clusters"),

    # HTMX partials
    path("locations/htmx/picker", views.htmx_location_picker, name="htmx_location_picker"),
    path("locations/htmx/options/districts", views.htmx_options_districts, name="htmx_options_districts"),
    path("locations/htmx/options/local-levels", views.htmx_options_local_levels, name="htmx_options_local_levels"),
    path("locations/htmx/options/areas", views.htmx_options_areas, name="htmx_options_areas"),
    path("locations/htmx/cluster-tags", views.htmx_cluster_tags, name="htmx_cluster_tags"),
]