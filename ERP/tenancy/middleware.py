from django.conf import settings
from django.db import connection
from .models import Tenant


class ActiveTenantMiddleware:
    """Attach the active tenant to the request and set the database schema."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self.process_request(request)
        response = self.get_response(request)
        return response

    def process_request(self, request):
        tenant_id = request.session.get('active_tenant') or request.META.get('HTTP_X_TENANT_ID')
        if not tenant_id:
            return
        try:
            tenant = Tenant.objects.get(pk=tenant_id)
        except Tenant.DoesNotExist:
            return
        request.tenant = tenant
        schema = tenant.data_schema
        engine = connection.settings_dict.get('ENGINE', '')
        connection.schema_name = schema
        if 'mssql' in engine:
            settings.SCHEMA_TO_INSPECT = f"'{schema}'"
        else:
            with connection.cursor() as cursor:
                cursor.execute('SET search_path TO %s', [schema])