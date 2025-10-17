import logging
from typing import List, Optional
from collections import namedtuple
from django.db import connection
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)

EntityField = namedtuple('EntityField', [
    'name',
    'data_type',
    'label',
    'required',
    'validation',
    'default_value',
    'help_text',
    'choices',
    'is_visible',
    'is_editable',
    'permission_required'
])

def load_entity_schema(entity_name: str, force_refresh: bool = False) -> List[EntityField]:
    """
    Load entity schema from database or cache.
    
    Args:
        entity_name: Name of the entity to load schema for
        force_refresh: If True, bypass cache and reload from database
        
    Returns:
        List of EntityField objects describing the entity's schema
    """
    cache_key = f'entity_schema_{entity_name}'
    
    # Try to get from cache first
    if not force_refresh:
        cached_schema = cache.get(cache_key)
        if cached_schema:
            return cached_schema
    
    try:
        with connection.cursor() as cursor:
            # Call stored procedure to get schema
            cursor.callproc('sp_GetEntitySchema', [entity_name])
            rows = cursor.fetchall()
            
            fields = []
            for row in rows:
                field = EntityField(
                    name=row[0],
                    data_type=row[1],
                    label=row[2],
                    required=bool(row[3]),
                    validation=row[4],
                    default_value=row[5] if len(row) > 5 else None,
                    help_text=row[6] if len(row) > 6 else None,
                    choices=row[7] if len(row) > 7 else None,
                    is_visible=bool(row[8]) if len(row) > 8 else True,
                    is_editable=bool(row[9]) if len(row) > 9 else True,
                    permission_required=row[10] if len(row) > 10 else None
                )
                fields.append(field)
            
            # Cache the result
            cache.set(cache_key, fields, timeout=3600)  # Cache for 1 hour
            
            return fields
            
    except Exception as e:
        logger.error(f"Error loading schema for entity {entity_name}: {str(e)}")
        raise

def get_field_permissions(entity_name: str, user) -> dict:
    """
    Get field-level permissions for a user on an entity.
    
    Args:
        entity_name: Name of the entity
        user: Django user object
        
    Returns:
        Dict mapping field names to permission levels (read/write/none)
    """
    try:
        with connection.cursor() as cursor:
            cursor.callproc('sp_GetFieldPermissions', [entity_name, user.id])
            rows = cursor.fetchall()
            
            permissions = {}
            for row in rows:
                field_name, permission = row
                permissions[field_name] = permission
                
            return permissions
            
    except Exception as e:
        logger.error(f"Error getting field permissions: {str(e)}")
        return {}

def get_entity_metadata(entity_name: str) -> dict:
    """
    Get comprehensive metadata for an entity including schema and UI configuration.
    
    Args:
        entity_name: Name of the entity
        
    Returns:
        Dict containing entity metadata
    """
    try:
        with connection.cursor() as cursor:
            cursor.callproc('sp_GetEntityMetadata', [entity_name])
            row = cursor.fetchone()
            
            if not row:
                return {}
                
            return {
                'name': row[0],
                'label': row[1],
                'description': row[2],
                'icon': row[3],
                'category': row[4],
                'is_active': bool(row[5]),
                'created_at': row[6],
                'updated_at': row[7],
                'version': row[8]
            }
            
    except Exception as e:
        logger.error(f"Error getting entity metadata: {str(e)}")
        return {} 