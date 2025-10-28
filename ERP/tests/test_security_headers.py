"""
Integration tests for security headers
"""
import pytest


@pytest.mark.integration
@pytest.mark.security
class TestSecurityHeaders:
    """Test suite for security headers middleware."""
    
    def test_x_content_type_options_header(self, client):
        """
        Test that X-Content-Type-Options header is set to nosniff.
        """
        response = client.get('/health/')
        assert response.get('X-Content-Type-Options') == 'nosniff'
    
    def test_x_frame_options_header(self, client):
        """
        Test that X-Frame-Options header is set to DENY.
        """
        response = client.get('/health/')
        assert response.get('X-Frame-Options') == 'DENY'
    
    def test_x_xss_protection_header(self, client):
        """
        Test that X-XSS-Protection header is set.
        """
        response = client.get('/health/')
        assert response.get('X-XSS-Protection') == '1; mode=block'
    
    def test_referrer_policy_header(self, client):
        """
        Test that Referrer-Policy header is set.
        """
        response = client.get('/health/')
        assert response.get('Referrer-Policy') == 'strict-origin-when-cross-origin'
    
    def test_permissions_policy_header(self, client):
        """
        Test that Permissions-Policy header restricts browser features.
        """
        response = client.get('/health/')
        permissions_policy = response.get('Permissions-Policy')
        
        if permissions_policy:
            assert 'geolocation=()' in permissions_policy
            assert 'microphone=()' in permissions_policy
            assert 'camera=()' in permissions_policy
    
    def test_csp_header(self, client):
        """
        Test that Content-Security-Policy header is set.
        """
        response = client.get('/health/')
        csp = response.get('Content-Security-Policy')
        
        if csp:
            assert "default-src 'self'" in csp
            assert "frame-ancestors 'none'" in csp
    
    def test_hsts_header_on_https(self, client):
        """
        Test that HSTS header is set on HTTPS requests.
        """
        # Simulate HTTPS request
        response = client.get('/health/', secure=True)
        hsts = response.get('Strict-Transport-Security')
        
        if hsts:
            assert 'max-age=31536000' in hsts
            assert 'includeSubDomains' in hsts
    
    def test_security_headers_on_api_endpoints(self, api_client):
        """
        Test that security headers are applied to API endpoints.
        """
        response = api_client.get('/api/v1/health/')
        
        # Check key security headers
        assert response.get('X-Content-Type-Options') == 'nosniff'
        assert response.get('X-Frame-Options') == 'DENY'
    
    def test_security_headers_on_admin(self, client, admin_user):
        """
        Test that security headers are applied to admin panel.
        """
        client.force_login(admin_user)
        response = client.get('/admin/')
        
        assert response.get('X-Content-Type-Options') == 'nosniff'
        assert response.get('X-Frame-Options') == 'DENY'
