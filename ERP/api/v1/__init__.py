"""
API Version 1 - Main API Module
"""
from rest_framework.routers import DefaultRouter

# Import viewsets here
# from .viewsets import YourViewSet

router = DefaultRouter()
# router.register(r'resource', YourViewSet)

urlpatterns = router.urls
