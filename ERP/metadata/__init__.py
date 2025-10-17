from django.apps import AppConfig

class MetadataConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'metadata'

    def ready(self):
        # Import here to avoid circular imports
        from .watcher import start_watcher, stop_watcher
        from .loader import load_entity_schema, get_field_permissions, get_entity_metadata
        from .persister import upsert_entity_properties, upsert_entity_metadata
        from .regenerator import (
            regenerate_pydantic_models,
            get_dynamic_model,
            get_form_template,
            generate_form_template
        )

        # Start the watcher when the app is ready
        start_watcher()

__all__ = [
    'start_watcher',
    'stop_watcher',
    'load_entity_schema',
    'get_field_permissions',
    'get_entity_metadata',
    'upsert_entity_properties',
    'upsert_entity_metadata',
    'regenerate_pydantic_models',
    'get_dynamic_model',
    'get_form_template',
    'generate_form_template'
] 