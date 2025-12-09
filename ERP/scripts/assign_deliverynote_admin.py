import os
import sys
import django

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard.settings')
django.setup()

from usermanagement.models import Permission, Role, Organization, UserOrganization
from usermanagement.utils import PermissionUtils

all_count = Permission.objects.count()
sample = list(Permission.objects.all().values_list('codename', flat=True)[:20])
print('Total permissions in DB:', all_count)
print('Sample permissions:', sample)
perms = list(Permission.objects.filter(codename__icontains='deliverynote'))
print('Found deliverynote perms:', [p.codename for p in perms])

summary = []
for org in Organization.objects.all():
    admin_role = Role.objects.filter(code='ADMIN', organization=org).first()
    if not admin_role:
        summary.append((org.name, 'no admin role'))
        continue

    before = set(admin_role.permissions.values_list('codename', flat=True))
    if perms:
        admin_role.permissions.add(*perms)
        admin_role.save()
    after = set(admin_role.permissions.values_list('codename', flat=True))
    added = sorted(list(after - before))

    # invalidate cache for users in this org
    user_count = 0
    for uo in UserOrganization.objects.filter(organization=org):
        try:
            PermissionUtils.invalidate_cache(uo.user.id, org.id)
            user_count += 1
        except Exception:
            pass

    summary.append((org.name, len(added), added, user_count))

print('\nAssignment summary:')
for item in summary:
    print(item)

print('\nDone.')
