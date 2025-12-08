from django.apps import AppConfig
import os


class NotificationCenterConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "notification_center"
    verbose_name = "Notification Center"

    def ready(self):
        # Import signal handlers
        # Signals can optionally be disabled using the DISABLE_NOTIFICATION_SIGNALS environment variable.
        if os.environ.get('DISABLE_NOTIFICATION_SIGNALS') != '1':
            from . import signals  # noqa: F401
