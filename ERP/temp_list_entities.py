from usermanagement.models import Entity
for entity in Entity.objects.all():
    print(f"Entity: {entity.name}, Code: {entity.code}, Module: {entity.module.name}")
