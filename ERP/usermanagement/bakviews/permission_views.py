"""
Deprecated bakviews permission views - re-export from the main views module.
"""
from ..views import (
    UserPermissionListView,
    UserRoleUpdateView,
    update_user_permissions,
    entity_permission_update,
)

__all__ = [
    'UserPermissionListView', 'UserRoleUpdateView', 'update_user_permissions', 'entity_permission_update'
]