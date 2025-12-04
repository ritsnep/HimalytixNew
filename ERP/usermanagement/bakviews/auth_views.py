"""
Deprecated bakviews auth views - re-export from main views module.
"""
from ..views import custom_login, logout_view

__all__ = ['custom_login', 'logout_view']