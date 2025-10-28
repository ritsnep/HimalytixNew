"""
API v1 URL Configuration
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .auth_streamlit import IssueStreamlitTokenView, VerifyStreamlitTokenView

app_name = 'api_v1'

# Create router
router = DefaultRouter()

# Register viewsets here
# Example:
# from .viewsets import AccountViewSet
# router.register(r'accounts', AccountViewSet, basename='account')

urlpatterns = [
    path('', include(router.urls)),
    # Add custom endpoints here if needed
    # path('custom/', CustomAPIView.as_view(), name='custom'),
    path('auth/streamlit/issue', IssueStreamlitTokenView.as_view(), name='auth_streamlit_issue'),
    path('auth/streamlit/verify', VerifyStreamlitTokenView.as_view(), name='auth_streamlit_verify'),
]
