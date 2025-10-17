from django.core.management.base import BaseCommand
from usermanagement.models import Entity

class Command(BaseCommand):
    help = 'Lists all entities in the system'

    def handle(self, *args, **kwargs):
        for entity in Entity.objects.all():
            self.stdout.write(f'Entity: {entity.name}, Code: {entity.code}, Module: {entity.module.name}')
