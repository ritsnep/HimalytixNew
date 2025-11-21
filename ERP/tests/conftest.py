"""
Pytest fixtures for Himalytix ERP testing
"""
import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from rest_framework.test import APIClient
from tenancy.models import Tenant

try:
    from rest_framework_simplejwt.tokens import RefreshToken
except ImportError:  # pragma: no cover - optional dependency in some environments
    RefreshToken = None


def _require_jwt():
    """Skip tests that rely on JWT when the dependency is missing."""
    if RefreshToken is None:
        pytest.skip("rest_framework_simplejwt is not installed in this environment")

User = get_user_model()


# =============================================================================
# DATABASE FIXTURES
# =============================================================================

@pytest.fixture(scope='function')
def db_setup(db):
    """
    Basic database setup for each test.
    Uses pytest-django's db fixture.
    """
    return db


@pytest.fixture(scope='session')
def django_db_setup():
    """
    Session-level database configuration.
    Override default test database settings.
    """
    from django.conf import settings
    settings.DATABASES['default'] = {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'test_himalytix',
        'USER': 'erp',
        'PASSWORD': 'test',
        'HOST': 'localhost',
        'PORT': '5432',
    }


# =============================================================================
# USER FIXTURES
# =============================================================================

@pytest.fixture
def user(db):
    """
    Create a regular test user.
    """
    return User.objects.create_user(
        username='testuser',
        email='testuser@example.com',
        password='testpass123',
        first_name='Test',
        last_name='User'
    )


@pytest.fixture
def admin_user(db):
    """
    Create an admin/superuser.
    """
    return User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='adminpass123',
        first_name='Admin',
        last_name='User'
    )


@pytest.fixture
def users(db):
    """
    Create multiple test users.
    """
    return [
        User.objects.create_user(
            username=f'user{i}',
            email=f'user{i}@example.com',
            password=f'pass{i}',
            first_name=f'User{i}',
            last_name='Test'
        )
        for i in range(1, 6)
    ]


# =============================================================================
# TENANT FIXTURES (Multi-Tenancy)
# =============================================================================

@pytest.fixture
def tenant(db):
    """
    Create a test tenant.
    """
    return Tenant.objects.create(
        name='Test Company',
        schema_name='test_company',
        domain='testcompany.localhost',
        is_active=True
    )


@pytest.fixture
def tenants(db):
    """
    Create multiple test tenants.
    """
    return [
        Tenant.objects.create(
            name=f'Company {i}',
            schema_name=f'company_{i}',
            domain=f'company{i}.localhost',
            is_active=True
        )
        for i in range(1, 4)
    ]


# =============================================================================
# CLIENT FIXTURES
# =============================================================================

@pytest.fixture
def client():
    """
    Django test client (for HTML views).
    """
    return Client()


@pytest.fixture
def authenticated_client(client, user):
    """
    Django test client with authenticated user.
    """
    client.force_login(user)
    return client


@pytest.fixture
def api_client():
    """
    DRF API client (for API endpoints).
    """
    return APIClient()


@pytest.fixture
def authenticated_api_client(api_client, user):
    """
    DRF API client with JWT authentication.
    """
    _require_jwt()
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return api_client


@pytest.fixture
def admin_api_client(api_client, admin_user):
    """
    DRF API client authenticated as admin.
    """
    _require_jwt()
    refresh = RefreshToken.for_user(admin_user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return api_client


# =============================================================================
# TOKEN FIXTURES (JWT)
# =============================================================================

@pytest.fixture
def user_token(user):
    """
    Generate JWT token for regular user.
    """
    _require_jwt()
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token)
    }


@pytest.fixture
def admin_token(admin_user):
    """
    Generate JWT token for admin user.
    """
    _require_jwt()
    refresh = RefreshToken.for_user(admin_user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token)
    }


# =============================================================================
# MOCK DATA FIXTURES
# =============================================================================

@pytest.fixture
def journal_entry_data():
    """
    Sample journal entry data for testing.
    """
    return {
        'date': '2024-01-15',
        'reference': 'JE-001',
        'description': 'Test journal entry',
        'amount': '1000.00',
        'account': 'Cash',
        'debit': '1000.00',
        'credit': '0.00'
    }


@pytest.fixture
def tenant_data():
    """
    Sample tenant data for testing.
    """
    return {
        'name': 'New Test Company',
        'schema_name': 'new_test_company',
        'domain': 'newtest.localhost',
        'is_active': True,
        'contact_email': 'admin@newtest.com',
        'contact_phone': '+1234567890'
    }


# =============================================================================
# UTILITY FIXTURES
# =============================================================================

@pytest.fixture
def settings_override():
    """
    Override Django settings for specific tests.
    Usage: settings_override({'DEBUG': True, 'ALLOWED_HOSTS': ['*']})
    """
    from django.test import override_settings
    return override_settings


@pytest.fixture
def mock_redis(mocker):
    """
    Mock Redis cache for testing without actual Redis.
    """
    mock = mocker.patch('django.core.cache.cache')
    mock.get.return_value = None
    mock.set.return_value = True
    mock.delete.return_value = True
    return mock


@pytest.fixture
def mock_celery(mocker):
    """
    Mock Celery tasks for testing without Celery workers.
    """
    return mocker.patch('celery.app.task.Task.apply_async')


@pytest.fixture
def capture_emails(settings):
    """
    Capture sent emails in memory for testing.
    """
    from django.core.mail import outbox
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    outbox.clear()
    return outbox


# =============================================================================
# PERFORMANCE FIXTURES
# =============================================================================

@pytest.fixture
def benchmark_query_count(django_assert_num_queries):
    """
    Assert maximum number of database queries.
    Usage: benchmark_query_count(5)  # Allow max 5 queries
    """
    return django_assert_num_queries


@pytest.fixture
def no_db_queries(django_assert_num_queries):
    """
    Assert that no database queries are made.
    """
    return django_assert_num_queries(0)


# =============================================================================
# CLEANUP FIXTURES
# =============================================================================

@pytest.fixture(autouse=True)
def reset_cache():
    """
    Clear cache after each test (auto-used).
    """
    from django.core.cache import cache
    yield
    cache.clear()


_test_environment_active = False


@pytest.fixture(autouse=True)
def reset_settings():
    """
    Ensure the Django test environment is toggled safely between tests.
    pytest-django already manages most of this, but some legacy tests expect
    explicit setup/teardown. Guard so we don't double-initialize when running
    under xdist.
    """
    global _test_environment_active
    from django.test.utils import setup_test_environment, teardown_test_environment

    if not _test_environment_active:
        try:
            setup_test_environment()
        except RuntimeError:
            # Environment was already set up by pytest-django; keep going.
            pass
        _test_environment_active = True
    try:
        yield
    finally:
        if _test_environment_active:
            try:
                teardown_test_environment()
            except RuntimeError:
                # Environment teardown already handled; ignore.
                pass
            _test_environment_active = False
