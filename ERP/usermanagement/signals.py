from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import UserRole, Role, Permission, UserPermission
from django.db import transaction

@receiver(post_save, sender=UserRole)
def assign_permissions_on_userrole_save(sender, instance, created, **kwargs):
    """
    When a UserRole is created or updated, ensure the user's permissions are in sync with the assigned role.
    Explicitly grant all permissions from the role to the user (if not already present).
    """
    user = instance.user
    role = instance.role
    org = instance.organization
    role_permissions = role.permissions.all()
    with transaction.atomic():
        for perm in role_permissions:
            UserPermission.objects.get_or_create(
                user=user,
                permission=perm,
                organization=org,
                defaults={'is_granted': True}
            )

@receiver(post_delete, sender=UserRole)
def remove_permissions_on_userrole_delete(sender, instance, **kwargs):
    """
    When a UserRole is deleted, remove permissions from the user that are only granted by that role.
    If the user has another role granting the same permission, keep it.
    """
    user = instance.user
    org = instance.organization
    role_permissions = set(instance.role.permissions.values_list('id', flat=True))
    # Find all permissions granted by other roles for this user/org
    other_roles = UserRole.objects.filter(user=user, organization=org).exclude(role=instance.role)
    other_perms = set()
    for ur in other_roles:
        other_perms.update(ur.role.permissions.values_list('id', flat=True))
    # Remove only those permissions that are not granted by any other role
    perms_to_remove = role_permissions - other_perms
    UserPermission.objects.filter(
        user=user,
        organization=org,
        permission_id__in=perms_to_remove,
        is_granted=True
    ).delete() 