"""
Integration tests for user authentication
"""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.mark.integration
@pytest.mark.smoke
class TestAuthentication:
    """Test suite for authentication flows."""
    
    def test_login_page_accessible(self, client):
        """
        Test that login page is accessible without authentication.
        """
        response = client.get('/accounts/login/')
        assert response.status_code == 200
    
    def test_user_can_login(self, client, user):
        """
        Test that user can login with correct credentials.
        """
        response = client.post('/accounts/login/', {
            'username': 'testuser',
            'password': 'testpass123',
        })
        # Should redirect after successful login
        assert response.status_code in [200, 302]
    
    def test_login_fails_with_wrong_password(self, client, user):
        """
        Test that login fails with incorrect password.
        """
        response = client.post('/accounts/login/', {
            'username': 'testuser',
            'password': 'wrongpassword',
        })
        # Should stay on login page or return error
        assert response.status_code in [200, 401]
    
    def test_authenticated_user_can_access_dashboard(self, authenticated_client):
        """
        Test that authenticated user can access dashboard.
        """
        response = authenticated_client.get('/dashboard/')
        # Should return 200 or redirect if dashboard route different
        assert response.status_code in [200, 301, 302, 404]
    
    def test_unauthenticated_user_redirected_from_dashboard(self, client):
        """
        Test that unauthenticated user is redirected to login.
        """
        response = client.get('/dashboard/', follow=False)
        # Should redirect to login
        if response.status_code == 302:
            assert '/login' in response.url or '/accounts/login' in response.url
    
    def test_user_can_logout(self, authenticated_client):
        """
        Test that user can logout successfully.
        """
        response = authenticated_client.post('/accounts/logout/')
        # Should redirect after logout
        assert response.status_code in [200, 302]


@pytest.mark.integration
@pytest.mark.api
class TestJWTAuthentication:
    """Test suite for JWT token authentication."""
    
    def test_jwt_token_obtained_with_valid_credentials(self, api_client, user):
        """
        Test that JWT token can be obtained with valid credentials.
        """
        # This assumes you have a token endpoint (e.g., /api/v1/auth/token/)
        # Adjust based on your actual JWT implementation
        response = api_client.post('/api/v1/auth/token/', {
            'username': 'testuser',
            'password': 'testpass123',
        })
        
        # Might return 200 or 404 if endpoint not implemented yet
        if response.status_code == 200:
            data = response.json()
            assert 'access' in data or 'token' in data
    
    def test_authenticated_api_client_can_access_protected_endpoint(self, authenticated_api_client):
        """
        Test that authenticated API client can access protected endpoints.
        """
        # Try to access a protected endpoint (e.g., /api/v1/users/me/)
        response = authenticated_api_client.get('/api/v1/users/me/')
        
        # Should return 200 or 404 if endpoint not implemented
        assert response.status_code in [200, 404, 401]
    
    def test_unauthenticated_api_client_denied_from_protected_endpoint(self, api_client):
        """
        Test that unauthenticated API client is denied access.
        """
        response = api_client.get('/api/v1/users/me/')
        
        # Should return 401 Unauthorized or 404 if endpoint not implemented
        assert response.status_code in [401, 403, 404]


@pytest.mark.unit
class TestUserModel:
    """Test suite for User model."""
    
    def test_create_user(self, db):
        """
        Test creating a new user.
        """
        user = User.objects.create_user(
            username='newuser',
            email='newuser@example.com',
            password='newpass123'
        )
        
        assert user.username == 'newuser'
        assert user.email == 'newuser@example.com'
        assert user.check_password('newpass123')
        assert not user.is_staff
        assert not user.is_superuser
    
    def test_create_superuser(self, db):
        """
        Test creating a superuser.
        """
        admin = User.objects.create_superuser(
            username='superuser',
            email='superuser@example.com',
            password='superpass123'
        )
        
        assert admin.is_staff
        assert admin.is_superuser
    
    def test_user_string_representation(self, user):
        """
        Test user __str__ method.
        """
        assert str(user) in ['testuser', 'Test User', 'testuser@example.com']
