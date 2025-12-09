import os
import django
import sys

# Ensure project root is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard.settings')
django.setup()

from django.contrib.auth import get_user_model
from usermanagement.models import Permission, Role, UserOrganization

User = get_user_model()

print('--- DeliveryNote permissions lookup ---')
perms = Permission.objects.filter(codename__icontains='deliverynote')
if not perms.exists():
    print('No Permission rows with "deliverynote" found')
else:
    for p in perms:
        print(f'Permission: codename={p.codename}, name={p.name}, module={p.module.code}, entity={p.entity.code}, action={p.action}')

print('\n--- Roles that include deliverynote permissions ---')
roles = Role.objects.filter(permissions__codename__icontains='deliverynote').distinct()
if not roles.exists():
    print('No Roles include deliverynote permissions')
else:
    for r in roles:
        print(f'Role: {r.name} (id={r.id})')

print('\n--- Superuser and superadmin defaults ---')
# Find any superusers
superusers = User.objects.filter(is_superuser=True)
print(f'Superusers count: {superusers.count()}')
for u in superusers[:5]:
    print(f'  superuser: username={u.username}, role={getattr(u, "role", None)}, active_org={u.get_active_organization()}')

# Find users with role superadmin
superadmins = User.objects.filter(role='superadmin')
print(f'Superadmin users count: {superadmins.count()}')
for u in superadmins[:5]:
    print(f'  superadmin: username={u.username}, is_superuser={u.is_superuser}, active_org={u.get_active_organization()}')

print('\n--- Check a sample admin user (username: admin) ---')
try:
    admin = User.objects.get(username='admin')
    print(f"admin: is_superuser={admin.is_superuser}, role={getattr(admin,'role',None)}, active_org={admin.get_active_organization()}")
    # list explicit permissions for admin within active org
    org = admin.get_active_organization()
    if org:
        perms_set = Permission.objects.filter(roles__user_roles__user=admin, roles__user_roles__organization=org, roles__user_roles__is_active=True).distinct()
        print('Explicit permissions via roles for admin in active org:')
        for p in perms_set[:50]:
            print(f'  {p.codename}')
    else:
        print('Admin has no active organization.')
except Exception as e:
    print('Admin user not found or error:', e)

print('\n--- Done ---')
