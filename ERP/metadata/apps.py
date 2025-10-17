from django.apps import AppConfig
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class MetadataConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'metadata'
    verbose_name = 'Metadata Management'

    def ready(self):
        """Initialize the metadata system when Django starts."""
        try:
            # Only start watcher in development
            if settings.DEBUG:
                from .watcher import start_watcher
                start_watcher()
                logger.info("Metadata watcher started in development mode")
        except Exception as e:
            logger.warning(f"Could not start metadata watcher: {str(e)}")
            logger.info("Metadata system will continue without file watching")
