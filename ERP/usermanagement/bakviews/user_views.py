"""
Deprecated bakviews wrapper for user views.
These are now provided by `usermanagement.views` to avoid duplication.
This module keeps backwards compatibility by re-exporting the views from the
main `views` module. Please import from `usermanagement.views` instead.
"""
from ..views import (
    UserListView,
    UserCreateView,
    UserDetailView,
    UserUpdateView,
    UserDeleteView,
)

__all__ = [
    'UserListView', 'UserCreateView', 'UserDetailView', 'UserUpdateView', 'UserDeleteView'
]