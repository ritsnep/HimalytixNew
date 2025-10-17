# usermanagement/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('users/', views.user_list, name='user_list'),
    path('users/create/', views.create_user, name='user_create'),
    path('users/delete/<int:pk>/', views.delete_user, name='user_delete'),
# usermanagement/urls.py
    path('login/', views.custom_login, name='login'),
    # path('login/', views.login_view, name='login'),

    path("logout/", views.logout_view, name="logout"),
    # path('companies/', views.company_list, name='company_list'),
    # path('companies/create/', views.company_create, name='company_create'),
    # path('companies/edit/<int:pk>/', views.company_edit, name='company_edit'),
    # path('companies/delete/<int:pk>/', views.company_delete, name='company_delete'),
    path('select-organization/', views.select_organization, name='select_organization'),

    
    path('roles/', views.RoleListView.as_view(), name='role_list'),
    path('roles/create/', views.RoleCreateView.as_view(), name='role_create'),
    path('roles/<int:pk>/edit/', views.RoleUpdateView.as_view(), name='role_update'),

    path('permissions/', views.PermissionListView.as_view(), name='permission_list'),
    path('permissions/create/', views.PermissionCreateView.as_view(), name='permission_create'),
    path('permissions/<int:pk>/edit/', views.PermissionUpdateView.as_view(), name='permission_update'),

    path('userroles/', views.UserRoleListView.as_view(), name='userrole_list'),
    path('userroles/create/', views.UserRoleCreateView.as_view(), name='userrole_create'),
    path('userroles/<int:pk>/edit/', views.UserRoleUpdateView.as_view(), name='userrole_update'),
]
