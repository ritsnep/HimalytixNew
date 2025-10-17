import logging
import time
from pathlib import Path
from typing import Optional, Callable
from django.conf import settings
from django.core.cache import cache
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)

# Initialize watchdog-related variables
WATCHDOG_AVAILABLE = False
FileSystemEventHandler = None
FileSystemEvent = None
Observer = None

# Try to import watchdog, but don't fail if not available
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    WATCHDOG_AVAILABLE = True
except ImportError as e:
    logger.warning(f"watchdog package not available. File watching will be disabled. Error: {str(e)}")

# Only define the handler class if watchdog is available
if WATCHDOG_AVAILABLE:
    class ModelChangeHandler(FileSystemEventHandler):
        def __init__(self, callback: Optional[Callable] = None):
            self.callback = callback
            self.last_modified = {}
            self.cooldown = 2  # seconds between processing same file

        def on_modified(self, event: FileSystemEvent):
            if not event.is_directory and event.src_path.endswith('.py'):
                current_time = time.time()
                last_modified = self.last_modified.get(event.src_path, 0)
                
                # Prevent multiple triggers for the same file within cooldown period
                if current_time - last_modified < self.cooldown:
                    return
                    
                self.last_modified[event.src_path] = current_time
                
                try:
                    # Extract entity name from file path
                    entity_name = self._extract_entity_name(event.src_path)
                    if entity_name:
                        logger.info(f"Detected changes in model: {entity_name}")
                        if self.callback:
                            self.callback(entity_name)
                        # Clear cache for this entity
                        cache.delete(f'entity_schema_{entity_name}')
                        cache.delete(f'entity_form_{entity_name}')
                except Exception as e:
                    logger.error(f"Error processing model change: {str(e)}")

        def _extract_entity_name(self, file_path: str) -> Optional[str]:
            """Extract entity name from file path and content."""
            try:
                path = Path(file_path)
                if 'models' in path.parts:
                    # Read file content to find model class
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # Look for class definitions that inherit from models.Model
                        import re
                        matches = re.finditer(r'class\s+(\w+)\s*\([^)]*models\.Model', content)
                        for match in matches:
                            return match.group(1)
            except Exception as e:
                logger.error(f"Error extracting entity name: {str(e)}")
            return None

class MetadataWatcher:
    def __init__(self):
        if not WATCHDOG_AVAILABLE:
            logger.warning("MetadataWatcher initialized without watchdog support")
            self.observer = None
            self.handler = None
            return
            
        self.observer = Observer()
        self.handler = ModelChangeHandler(callback=self._on_model_change)
        self.watched_paths = set()

    def start(self):
        """Start watching model directories."""
        if not WATCHDOG_AVAILABLE:
            logger.warning("Cannot start watcher: watchdog not available")
            return
            
        try:
            # Watch all model directories in installed apps
            for app in settings.INSTALLED_APPS:
                try:
                    app_path = import_string(f"{app}.models").__file__
                    if app_path:
                        model_dir = str(Path(app_path).parent)
                        if model_dir not in self.watched_paths:
                            self.observer.schedule(
                                self.handler,
                                path=model_dir,
                                recursive=False
                            )
                            self.watched_paths.add(model_dir)
                            logger.info(f"Watching models in: {model_dir}")
                except (ImportError, AttributeError):
                    continue

            self.observer.start()
            logger.info("Metadata watcher started successfully")
        except Exception as e:
            logger.error(f"Error starting metadata watcher: {str(e)}")

    def stop(self):
        """Stop watching model directories."""
        if not WATCHDOG_AVAILABLE:
            return
            
        try:
            self.observer.stop()
            self.observer.join()
            logger.info("Metadata watcher stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping metadata watcher: {str(e)}")

    def _on_model_change(self, entity_name: str):
        """Handle model changes by regenerating metadata."""
        try:
            from .loader import load_entity_schema
            from .persister import upsert_entity_properties
            from .regenerator import regenerate_pydantic_models

            # Reload schema and update properties
            fields = load_entity_schema(entity_name)
            upsert_entity_properties(entity_name, fields)
            
            # Regenerate models
            regenerate_pydantic_models()
            
            logger.info(f"Successfully processed changes for entity: {entity_name}")
        except Exception as e:
            logger.error(f"Error processing model changes: {str(e)}")

# Singleton instance
watcher = MetadataWatcher()

def start_watcher():
    """Start the metadata watcher."""
    if WATCHDOG_AVAILABLE:
        watcher.start()
    else:
        logger.warning("Cannot start watcher: watchdog not available")

def stop_watcher():
    """Stop the metadata watcher."""
    if WATCHDOG_AVAILABLE:
        watcher.stop()
    else:
        logger.warning("Cannot stop watcher: watchdog not available") 