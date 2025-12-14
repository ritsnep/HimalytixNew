from __future__ import annotations

from typing import Dict, Any

from django.apps import apps
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Load default print templates and user print configuration for onboarding."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            dest="username",
            help="Create seed templates for the given username (defaults to all superusers).",
        )
        parser.add_argument(
            "--org-id",
            dest="org_id",
            type=int,
            help="Optional organization id to attach templates to.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            dest="force",
            help="Overwrite existing templates/configs for the user(s).",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        username = options.get("username")
        org_id = options.get("org_id")
        force = options.get("force")

        PrintingApp = apps.get_app_config("printing")
        PrintTemplate = apps.get_model("printing", "PrintTemplate")
        PrintTemplateConfig = apps.get_model("printing", "PrintTemplateConfig")

        from printing import utils as printing_utils

        targets = []
        if username:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"User '{username}' not found."))
                return
            targets.append(user)
        else:
            targets = list(User.objects.filter(is_superuser=True))

        if not targets:
            self.stdout.write("No target users found for seeding. Provide --username or ensure at least one superuser exists.")
            return

        created_templates = 0
        created_configs = 0

        default_toggles: Dict[str, Any] = {**printing_utils.DEFAULT_TOGGLES}

        for user in targets:
            if force:
                # Remove existing templates for user/org/doc combinations when forcing
                PrintTemplate.objects.filter(user=user, organization_id=org_id).delete()
                PrintTemplateConfig.objects.filter(user=user).delete()

            # Create a default PrintTemplateConfig if not present
            config_obj, config_data = printing_utils.get_user_print_config(user)
            if config_obj is None:
                cfg = PrintTemplateConfig(user=user)
                cfg.template_name = printing_utils.DEFAULT_TEMPLATE
                cfg.config = {**default_toggles, **printing_utils.DEFAULT_OPTIONS}
                if org_id:
                    # If PrintTemplateConfig has an organization field in future, keep it safe
                    try:
                        setattr(cfg, "organization_id", org_id)
                    except Exception:
                        pass
                cfg.save()
                created_configs += 1

            # Create one template per DOCUMENT_TYPE (classic + compact)
            for doc_type in printing_utils.DOCUMENT_TYPE_MODELS.keys():
                for tpl in printing_utils.ALLOWED_TEMPLATES:
                    name = f"{doc_type} - {tpl}"
                    exists = PrintTemplate.objects.filter(
                        user=user, organization_id=org_id, document_type=doc_type, name=name
                    ).exists()
                    if exists and not force:
                        continue

                    tpl_obj = PrintTemplate(
                        user=user,
                        organization_id=org_id,
                        document_type=doc_type,
                        name=name,
                        paper_size=printing_utils.DEFAULT_OPTIONS.get("paper_size", "A4"),
                        config={**default_toggles, "template_name": tpl, "paper_size": printing_utils.DEFAULT_OPTIONS.get("paper_size", "A4")},
                    )
                    tpl_obj.save()
                    created_templates += 1

        self.stdout.write(self.style.SUCCESS(f"Created {created_templates} print template(s) and {created_configs} print config(s)."))
