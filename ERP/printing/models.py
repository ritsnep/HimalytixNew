from django.conf import settings
from django.db import models


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
