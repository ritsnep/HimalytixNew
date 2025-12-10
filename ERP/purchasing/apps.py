from django.apps import AppConfig


class PurchasingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "purchasing"
    verbose_name = "Purchasing"

    def ready(self):
        """Register signals for audit logging."""
        from . import signals  # noqa
