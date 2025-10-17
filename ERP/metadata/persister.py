import logging
from typing import List
from django.db import models, transaction
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

class EntityProperty(models.Model):
    """Model to store entity field metadata."""
    entity_name = models.CharField(max_length=100, db_index=True)
    property_name = models.CharField(max_length=100)
    data_type = models.CharField(max_length=50)
    label = models.CharField(max_length=100)
    validation_rules = models.TextField(null=True, blank=True)
    required = models.BooleanField(default=False)
    default_value = models.TextField(null=True, blank=True)
    help_text = models.TextField(null=True, blank=True)
    choices = models.TextField(null=True, blank=True)  # JSON string of choices
    is_visible = models.BooleanField(default=True)
    is_editable = models.BooleanField(default=True)
    permission_required = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.IntegerField(default=1)

    class Meta:
        unique_together = ('entity_name', 'property_name')
        indexes = [
            models.Index(fields=['entity_name', 'property_name']),
            models.Index(fields=['entity_name', 'is_visible']),
            models.Index(fields=['entity_name', 'is_editable']),
        ]

    def __str__(self):
        return f"{self.entity_name}.{self.property_name}"

class EntityMetadata(models.Model):
    """Model to store entity-level metadata."""
    entity_name = models.CharField(max_length=100, unique=True)
    label = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    icon = models.CharField(max_length=50, null=True, blank=True)
    category = models.CharField(max_length=50, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.IntegerField(default=1)

    def __str__(self):
        return self.entity_name

@transaction.atomic
def upsert_entity_properties(entity_name: str, fields: List['EntityField']) -> None:
    """
    Update or create entity properties based on schema changes.
    
    Args:
        entity_name: Name of the entity
        fields: List of EntityField objects from schema
    """
    try:
        # Import here to avoid circular imports
        from .loader import EntityField
        
        # Get existing properties
        existing_props = {
            prop.property_name: prop
            for prop in EntityProperty.objects.filter(entity_name=entity_name)
        }
        
        # Process each field
        for field in fields:
            defaults = {
                'data_type': field.data_type,
                'label': field.label,
                'required': field.required,
                'validation_rules': field.validation,
                'default_value': field.default_value,
                'help_text': field.help_text,
                'choices': field.choices,
                'is_visible': field.is_visible,
                'is_editable': field.is_editable,
                'permission_required': field.permission_required,
                'updated_at': timezone.now()
            }
            
            if field.name in existing_props:
                # Update existing property
                prop = existing_props[field.name]
                for key, value in defaults.items():
                    setattr(prop, key, value)
                prop.version += 1
                prop.save()
            else:
                # Create new property
                EntityProperty.objects.create(
                    entity_name=entity_name,
                    property_name=field.name,
                    **defaults
                )
        
        # Remove properties that no longer exist
        current_props = {field.name for field in fields}
        for prop_name, prop in existing_props.items():
            if prop_name not in current_props:
                prop.delete()
        
        # Clear cache
        cache.delete(f'entity_schema_{entity_name}')
        cache.delete(f'entity_form_{entity_name}')
        
        logger.info(f"Successfully updated properties for entity: {entity_name}")
        
    except Exception as e:
        logger.error(f"Error updating entity properties: {str(e)}")
        raise

@transaction.atomic
def upsert_entity_metadata(metadata: dict) -> None:
    """
    Update or create entity metadata.
    
    Args:
        metadata: Dict containing entity metadata
    """
    try:
        defaults = {
            'label': metadata['label'],
            'description': metadata.get('description'),
            'icon': metadata.get('icon'),
            'category': metadata.get('category'),
            'is_active': metadata.get('is_active', True),
            'updated_at': timezone.now()
        }
        
        entity, created = EntityMetadata.objects.update_or_create(
            entity_name=metadata['name'],
            defaults=defaults
        )
        
        if not created:
            entity.version += 1
            entity.save()
        
        # Clear cache
        cache.delete(f'entity_metadata_{metadata["name"]}')
        
        logger.info(f"Successfully updated metadata for entity: {metadata['name']}")
        
    except Exception as e:
        logger.error(f"Error updating entity metadata: {str(e)}")
        raise 