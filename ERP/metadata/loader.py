import logging
from typing import List, Optional
from collections import namedtuple
from django.apps import apps
from django.core.cache import cache
from django.db import connection

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

    if not force_refresh:
        cached_schema = cache.get(cache_key)
        if cached_schema:
            return cached_schema

    try:
        EntityProperty = apps.get_model('metadata', 'EntityProperty')
        properties = list(
            EntityProperty.objects.filter(entity_name=entity_name)
            .order_by('property_name')
            .values(
                'property_name',
                'data_type',
                'label',
                'required',
                'validation_rules',
                'default_value',
                'help_text',
                'choices',
                'is_visible',
                'is_editable',
                'permission_required',
            )
        )

        if not properties:
            with connection.cursor() as cursor:
                cursor.callproc('sp_GetEntitySchema', [entity_name])
                rows = cursor.fetchall()
                properties = [
                    {
                        'property_name': row[0],
                        'data_type': row[1],
                        'label': row[2],
                        'required': bool(row[3]),
                        'validation_rules': row[4],
                        'default_value': row[5] if len(row) > 5 else None,
                        'help_text': row[6] if len(row) > 6 else None,
                        'choices': row[7] if len(row) > 7 else None,
                        'is_visible': bool(row[8]) if len(row) > 8 else True,
                        'is_editable': bool(row[9]) if len(row) > 9 else True,
                        'permission_required': row[10] if len(row) > 10 else None,
                    }
                    for row in rows
                ]

        fields = [
            EntityField(
                name=prop['property_name'],
                data_type=prop['data_type'],
                label=prop['label'],
                required=bool(prop['required']),
                validation=prop['validation_rules'],
                default_value=prop['default_value'],
                help_text=prop['help_text'],
                choices=prop['choices'],
                is_visible=bool(prop['is_visible']),
                is_editable=bool(prop['is_editable']),
                permission_required=prop['permission_required'],
            )
            for prop in properties
        ]

        cache.set(cache_key, fields, timeout=None)
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
    cache_key = f'entity_metadata_{entity_name}'
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        EntityMetadata = apps.get_model('metadata', 'EntityMetadata')
        try:
            metadata_obj = EntityMetadata.objects.get(entity_name=entity_name)
            metadata = {
                'name': metadata_obj.entity_name,
                'label': metadata_obj.label,
                'description': metadata_obj.description,
                'icon': metadata_obj.icon,
                'category': metadata_obj.category,
                'is_active': metadata_obj.is_active,
                'created_at': metadata_obj.created_at,
                'updated_at': metadata_obj.updated_at,
                'version': metadata_obj.version
            }
        except EntityMetadata.DoesNotExist:
            with connection.cursor() as cursor:
                cursor.callproc('sp_GetEntityMetadata', [entity_name])
                row = cursor.fetchone()
                if not row:
                    return {}
                metadata = {
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

        cache.set(cache_key, metadata, timeout=None)
        return metadata

    except Exception as e:
        logger.error(f"Error getting entity metadata: {str(e)}")
        return {}