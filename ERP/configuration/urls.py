from rest_framework.routers import DefaultRouter
from django.urls import include, path

from .views import ConfigurationEntryViewSet, FeatureToggleViewSet

router = DefaultRouter()
router.register("entries", ConfigurationEntryViewSet, basename="configuration-entry")
router.register("feature-toggles", FeatureToggleViewSet, basename="feature-toggle")

urlpatterns = [
    path("", include(router.urls)),
]
