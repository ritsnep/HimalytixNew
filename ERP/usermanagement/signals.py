from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver

from usermanagement.models import UserRole, UserPermission, Role
from usermanagement.utils import PermissionUtils


def _invalidate(user_id, organization_id):
    if not user_id or not organization_id:
        return
    PermissionUtils.invalidate_cache(user_id, organization_id)


@receiver(post_save, sender=UserRole)
def invalidate_cache_on_userrole_save(sender, instance, **kwargs):
    _invalidate(instance.user_id, instance.organization_id)


@receiver(post_delete, sender=UserRole)
def invalidate_cache_on_userrole_delete(sender, instance, **kwargs):
    _invalidate(instance.user_id, instance.organization_id)


@receiver(post_save, sender=UserPermission)
def invalidate_cache_on_userpermission_save(sender, instance, **kwargs):
    _invalidate(instance.user_id, instance.organization_id)


@receiver(post_delete, sender=UserPermission)
def invalidate_cache_on_userpermission_delete(sender, instance, **kwargs):
    _invalidate(instance.user_id, instance.organization_id)


@receiver(m2m_changed, sender=Role.permissions.through)
def invalidate_cache_on_role_permission_change(sender, instance, action, **kwargs):
    if action not in {'post_add', 'post_remove', 'post_clear'}:
        return
    for user_role in instance.user_roles.all():
        _invalidate(user_role.user_id, user_role.organization_id)
