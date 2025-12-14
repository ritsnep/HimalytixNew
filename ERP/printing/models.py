from django.conf import settings
from django.db import models

from .models_audit import PrintSettingsAuditLog  # noqa: F401


class PrintTemplateConfig(models.Model):
    """Stores user-specific print configuration: selected template style and toggle options."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="print_template_config",
    )
    template_name = models.CharField(
        max_length=20,
        choices=[("classic", "Classic"), ("compact", "Compact")],
        default="classic",
        help_text="Selected print template style (e.g. classic or compact).",
    )
    config = models.JSONField(
        default=dict,
        blank=True,
        help_text="JSON of toggle states for various print options.",
    )

    class Meta:
        verbose_name = "Print Template Configuration"
        verbose_name_plural = "Print Template Configurations"
        permissions = [
            ("can_edit_print_templates", "Can edit print template settings"),
        ]

    def __str__(self) -> str:
        username = getattr(self.user, "username", None) or str(self.user)
        return f"{username} – {self.template_name} template config"


class PrintTemplate(models.Model):
    """Master templates for different document types with user-defined names and configs."""

    DOCUMENT_TYPES = [
        ('journal', 'Journal'),
        ('purchase_order', 'Purchase Order'),
        ('sales_order', 'Sales Order'),
        ('sales_invoice', 'Sales Invoice'),
        # Add more as needed
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    organization = models.ForeignKey(
        'usermanagement.Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    document_type = models.CharField(
        max_length=50,
        choices=DOCUMENT_TYPES,
    )
    name = models.CharField(
        max_length=100,
        help_text="User-defined name for this template.",
    )
    paper_size = models.CharField(
        max_length=10,
        choices=[("A4", "A4"), ("A5", "A5")],
        default="A4",
    )
    config = models.JSONField(
        default=dict,
        blank=True,
        help_text="JSON of template settings including toggles and template_name.",
    )

    class Meta:
        unique_together = ('user', 'organization', 'document_type', 'name')
        verbose_name = "Print Template"
        verbose_name_plural = "Print Templates"

    def __str__(self) -> str:
        username = getattr(self.user, "username", None) or str(self.user)
        return f"{username} – {self.document_type} – {self.name}"
