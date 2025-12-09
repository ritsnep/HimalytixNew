from django.core.management.base import BaseCommand
from django.template import loader
from django.template import TemplateDoesNotExist
from django.conf import settings
import os

class Command(BaseCommand):
    help = 'Validate template inheritance chain'

    def handle(self, *args, **options):
        """Check all templates can be loaded and show inheritance."""
        errors = []

        # Get template directories from settings
        template_dirs = []
        for engine_config in settings.TEMPLATES:
            if engine_config.get('BACKEND') == 'django.template.backends.django.DjangoTemplates':
                template_dirs.extend(engine_config.get('DIRS', []))

        for template_dir in template_dirs:
            if not os.path.exists(template_dir):
                continue

            for root, dirs, files in os.walk(template_dir):
                for file in files:
                    if file.endswith('.html'):
                        # Get relative path from template directory
                        rel_path = os.path.relpath(
                            os.path.join(root, file),
                            template_dir
                        )

                        try:
                            template = loader.get_template(rel_path)
                            self.stdout.write(
                                self.style.SUCCESS(f'✓ {rel_path}')
                            )
                        except TemplateDoesNotExist as e:
                            errors.append(f'{rel_path}: {e}')
                            self.stdout.write(
                                self.style.ERROR(f'✗ {rel_path}: {e}')
                            )
                        except Exception as e:
                            errors.append(f'{rel_path}: {e}')
                            self.stdout.write(
                                self.style.ERROR(f'✗ {rel_path}: {e}')
                            )

        if errors:
            self.stdout.write(self.style.ERROR(f'\n{len(errors)} errors found'))
            return

        self.stdout.write(self.style.SUCCESS('\nAll templates valid!'))