from django.db import connection

def get_entity_schema(entity_name: str, tenant_id: int = None):
    """
    Calls the stored procedure sp_GetEntitySchema and returns a list of field metadata dicts.
    """
    with connection.cursor() as cursor:
        cursor.execute("EXEC sp_GetEntitySchema @EntityName=%s, @TenantId=%s", [entity_name, tenant_id])
        cols = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        schema = [dict(zip(cols, row)) for row in rows]
    return schema
