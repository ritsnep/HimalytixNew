"""
Integration tests for health check endpoints
"""
import pytest
from django.urls import reverse


@pytest.mark.integration
@pytest.mark.smoke
class TestHealthEndpoints:
    """Test suite for health check endpoints."""
    
    def test_health_endpoint_returns_200(self, client):
        """
        Test that /health/ returns 200 OK.
        """
        response = client.get('/health/')
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json'
    
    def test_health_endpoint_response_structure(self, client):
        """
        Test that /health/ returns correct JSON structure.
        """
        response = client.get('/health/')
        data = response.json()
        
        assert 'status' in data
        assert data['status'] == 'healthy'
        assert 'service' in data
        assert data['service'] == 'himalytix-erp'
        assert 'timestamp' in data
    
    def test_health_ready_endpoint_returns_200(self, client, db):
        """
        Test that /health/ready/ returns 200 when all services are up.
        """
        response = client.get('/health/ready/')
        assert response.status_code == 200
    
    def test_health_ready_endpoint_response_structure(self, client, db):
        """
        Test that /health/ready/ returns correct JSON structure.
        """
        response = client.get('/health/ready/')
        data = response.json()
        
        assert 'status' in data
        assert data['status'] in ['ready', 'not_ready']
        assert 'service' in data
        assert 'timestamp' in data
        assert 'checks' in data
        
        # Check components
        checks = data['checks']
        assert 'database' in checks
        assert 'redis_cache' in checks
        assert 'celery' in checks
        assert 'disk' in checks
    
    def test_health_ready_database_check(self, client, db):
        """
        Test that database check passes when DB is available.
        """
        response = client.get('/health/ready/')
        data = response.json()
        
        db_check = data['checks']['database']
        assert db_check['status'] == 'ok'
        assert 'PostgreSQL' in db_check['message']
    
    def test_health_live_endpoint(self, client):
        """
        Test that /health/live/ returns 200 (liveness probe).
        """
        response = client.get('/health/live/')
        assert response.status_code == 200
        
        data = response.json()
        assert data['status'] == 'alive'
        assert 'timestamp' in data
    
    @pytest.mark.slow
    def test_health_endpoints_performance(self, client, benchmark_query_count):
        """
        Test that health endpoints respond quickly (<100ms).
        """
        import time
        
        # Test /health/ (no DB queries)
        start = time.time()
        response = client.get('/health/')
        duration = time.time() - start
        
        assert response.status_code == 200
        assert duration < 0.1  # <100ms
    
    def test_health_endpoint_no_authentication_required(self, client):
        """
        Test that health endpoints don't require authentication.
        """
        # No login required
        response = client.get('/health/')
        assert response.status_code == 200
        
        response = client.get('/health/ready/')
        assert response.status_code in [200, 503]  # OK or Service Unavailable
        
        response = client.get('/health/live/')
        assert response.status_code == 200
