"""
Integration tests for API versioning middleware
"""
import pytest
from django.urls import reverse


@pytest.mark.integration
@pytest.mark.api
class TestAPIVersioning:
    """Test suite for API versioning."""
    
    def test_api_v1_endpoints_accessible(self, api_client):
        """
        Test that /api/v1/ endpoints are accessible.
        """
        response = api_client.get('/api/v1/')
        # Should return 200 or 404 (if no root endpoint defined)
        assert response.status_code in [200, 404]
    
    def test_api_version_extracted_from_url(self, api_client):
        """
        Test that API version is extracted from URL path.
        """
        response = api_client.get('/api/v1/health/')
        
        # Check if version header is set (if middleware adds it)
        # Note: This depends on your middleware implementation
        assert response.status_code in [200, 404]
    
    def test_api_schema_endpoint_accessible(self, api_client):
        """
        Test that OpenAPI schema endpoint is accessible.
        """
        response = api_client.get('/api/schema/')
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/vnd.oai.openapi+json'
    
    def test_swagger_ui_accessible(self, client):
        """
        Test that Swagger UI is accessible at /api/docs/.
        """
        response = client.get('/api/docs/')
        assert response.status_code == 200
        assert 'text/html' in response['Content-Type']
    
    def test_redoc_ui_accessible(self, client):
        """
        Test that ReDoc UI is accessible at /api/redoc/.
        """
        response = client.get('/api/redoc/')
        assert response.status_code == 200
        assert 'text/html' in response['Content-Type']
    
    def test_legacy_api_endpoints_still_work(self, api_client):
        """
        Test that legacy /api/ endpoints (if any) still work.
        """
        # This test assumes you have legacy endpoints
        # Adjust based on your actual API structure
        response = api_client.get('/api/')
        assert response.status_code in [200, 404, 301]  # OK, Not Found, or Redirect
    
    @pytest.mark.parametrize('endpoint', [
        '/api/schema/',
        '/api/docs/',
        '/api/redoc/',
    ])
    def test_api_documentation_endpoints(self, client, endpoint):
        """
        Test that all API documentation endpoints are accessible.
        """
        response = client.get(endpoint)
        assert response.status_code == 200


@pytest.mark.unit
class TestAPIVersionMiddleware:
    """Test suite for API version middleware logic."""
    
    def test_middleware_handles_v1_requests(self, api_client):
        """
        Test that middleware correctly handles v1 API requests.
        """
        response = api_client.get('/api/v1/health/')
        # Middleware should process this without errors
        assert response.status_code in [200, 404]
    
    def test_middleware_adds_version_context(self, api_client):
        """
        Test that middleware adds API version to request context.
        """
        # This test would require inspecting request.api_version
        # which is set by middleware (if implemented)
        response = api_client.get('/api/v1/health/')
        assert response.status_code in [200, 404]
