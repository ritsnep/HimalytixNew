#!/usr/bin/env python
"""Inspect all users, org mappings, role assignments, and admin's effective permissions."""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp.settings')

import django
django.setup()

from usermanagement.models import CustomUser, UserOrganization, UserRole, Role
from usermanagement.utils import PermissionUtils


def main():
    users = CustomUser.objects.all()
    print('=== ALL USERS ===')
    for u in users:
        org = u.get_active_organization()
        org_name = org.name if org else 'None'
        print(f'{u.username}: is_superuser={u.is_superuser}, role={u.role}, active_org={org_name}')

    print()
    print('=== USER ORG MAPPINGS ===')
    for uo in UserOrganization.objects.select_related('user', 'organization').all():
        print(f'{uo.user.username} -> {uo.organization.name} (role={uo.role}, is_active={uo.is_active})')

    print()
    print('=== USER ROLE ASSIGNMENTS (UserRole table) ===')
    user_roles = UserRole.objects.select_related('user', 'role', 'organization').all()
    if not user_roles.exists():
        print('(No UserRole assignments found - users may not have explicit role assignments)')
    for ur in user_roles:
        print(f'{ur.user.username} -> {ur.role.name} ({ur.role.code}) in {ur.organization.name}, is_active={ur.is_active}')

    print()
    print('=== AVAILABLE ROLES PER ORG ===')
    for role in Role.objects.select_related('organization').all():
        perm_count = role.permissions.count()
        print(f'{role.organization.name}: {role.name} ({role.code}) - {perm_count} permissions')

    print()
    print('=== ADMIN USER EFFECTIVE PERMISSIONS ===')
    admin_user = CustomUser.objects.filter(username='admin').first()
    if admin_user:
        org = admin_user.get_active_organization()
        perms = PermissionUtils.get_user_permissions(admin_user, org)
        if perms == ['*']:
            print('admin has FULL ACCESS (superuser or superadmin role)')
        else:
            print(f'admin has {len(perms)} permissions')
            dn_perms = [p for p in perms if 'deliverynote' in p]
            print(f'deliverynote perms: {dn_perms}')
    else:
        print('No admin user found')


if __name__ == '__main__':
    main()
