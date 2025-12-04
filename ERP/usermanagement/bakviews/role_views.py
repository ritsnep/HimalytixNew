"""
Deprecated bakviews wrapper for role views.
Re-exporting from the main `usermanagement.views` module to maintain
temporary backwards compatibility. Import from `usermanagement.views` instead.
"""
from ..views import (
    RoleListView,
    RoleCreateView,
    RoleDetailView,
    RoleUpdateView,
    RoleDeleteView,
)

__all__ = [
    'RoleListView', 'RoleCreateView', 'RoleDetailView', 'RoleUpdateView', 'RoleDeleteView'
]