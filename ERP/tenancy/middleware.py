from django.conf import settings
from django.db import connection
from usermanagement.models import UserOrganization

from .models import Tenant


class ActiveTenantMiddleware:
    """Attach the active tenant to the request and safely scope DB schema."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self._activate_tenant(request)
        try:
            response = self.get_response(request)
        finally:
            self._reset_schema()
        return response

    def _activate_tenant(self, request):
        tenant_id = (request.session or {}).get('active_tenant') if hasattr(request, 'session') else None
        if not tenant_id:
            request.tenant = None
            return

        tenant = Tenant.objects.filter(pk=tenant_id, is_active=True).first()
        if not tenant:
            request.session.pop('active_tenant', None)
            request.tenant = None
            return

        user = getattr(request, 'user', None)
        if user and user.is_authenticated and not user.is_superuser:
            has_membership = UserOrganization.objects.filter(
                user_id=user.id,
                organization__tenant=tenant,
                is_active=True,
            ).exists()
            if not has_membership:
                request.session.pop('active_tenant', None)
                request.tenant = None
                return

        request.tenant = tenant
        self._set_schema(tenant.data_schema)

    def _set_schema(self, schema_name: str):
        engine = connection.settings_dict.get('ENGINE', '')
        # SQLite and other simple backends do not support schemas; skip quietly.
        if 'sqlite' in engine:
            return
        connection.schema_name = schema_name
        if 'mssql' in engine:
            settings.SCHEMA_TO_INSPECT = f"'{schema_name}'"
        else:
            with connection.cursor() as cursor:
                cursor.execute('SET search_path TO %s', [schema_name])

    def _reset_schema(self):
        engine = connection.settings_dict.get('ENGINE', '')
        # SQLite and other simple backends do not support schemas; skip quietly.
        if 'sqlite' in engine:
            return
        connection.schema_name = None
        if 'mssql' in engine:
            settings.SCHEMA_TO_INSPECT = "'dbo'"
        else:
            default_schema = getattr(settings, 'DEFAULT_DB_SCHEMA', 'public')
            with connection.cursor() as cursor:
                cursor.execute('SET search_path TO %s', [default_schema])
