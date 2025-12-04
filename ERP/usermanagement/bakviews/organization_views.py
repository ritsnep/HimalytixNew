"""
Deprecated bakviews wrapper for organization views. Re-export the views from
`usermanagement.views` and mark this module as deprecated.
"""
from ..views import (
    OrganizationListView,
    OrganizationCreateView,
    OrganizationDetailView,
    OrganizationUpdateView,
    OrganizationDeleteView,
)

__all__ = [
    'OrganizationListView', 'OrganizationCreateView', 'OrganizationDetailView',
    'OrganizationUpdateView', 'OrganizationDeleteView'
]