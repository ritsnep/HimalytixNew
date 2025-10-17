from django.test import TestCase, RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware
from django.conf import settings
from django.db import connection

# Create your tests here.
from .middleware import ActiveTenantMiddleware
from .models import Tenant


class ActiveTenantMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = ActiveTenantMiddleware(lambda r: None)

    def _get_request(self):
        request = self.factory.get('/')
        middleware = SessionMiddleware(lambda r: None)
        middleware.process_request(request)
        request.session.save()
        return request

    def test_schema_set_from_session(self):
        tenant = Tenant.objects.create(
            code='t1',
            name='Tenant 1',
            slug='tenant-1',
            data_schema='t1schema'
        )
        request = self._get_request()
        request.session['active_tenant'] = tenant.id
        self.middleware.process_request(request)
        self.assertEqual(getattr(request, 'tenant'), tenant)
        if 'mssql' in connection.settings_dict['ENGINE']:
            self.assertEqual(settings.SCHEMA_TO_INSPECT, f"'{tenant.data_schema}'")
        else:
            self.assertEqual(connection.schema_name, tenant.data_schema)