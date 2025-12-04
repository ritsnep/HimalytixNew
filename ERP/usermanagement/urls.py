app_name = 'usermanagement'
# usermanagement/urls.py
from django.urls import path
from . import views
# bakviews was used for legacy view implementations. All views now live in views.py

urlpatterns = [
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/create/', views.UserCreateView.as_view(), name='user_create'),
    path('users/<int:pk>/', views.UserDetailView.as_view(), name='user_detail'),
    path('users/<int:pk>/edit/', views.UserUpdateView.as_view(), name='user_update'),
    path('users/<int:pk>/delete/', views.UserDeleteView.as_view(), name='user_delete'),
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
    path('roles/<int:pk>/', views.RoleDetailView.as_view(), name='role_detail'),
    path('roles/<int:pk>/delete/', views.RoleDeleteView.as_view(), name='role_delete'),

    path('permissions/', views.UserPermissionListView.as_view(), name='permission_list'),
    path('permissions/create/', views.PermissionCreateView.as_view(), name='permission_create'),
    path('permissions/<int:pk>/edit/', views.PermissionUpdateView.as_view(), name='permission_update'),
    path('permissions/entity/<int:entity_id>/role/<int:role_id>/update/', views.entity_permission_update, name='entity_permission_update'),

    path('userroles/', views.UserRoleListView.as_view(), name='userrole_list'),
    path('userroles/create/', views.UserRoleCreateView.as_view(), name='userrole_create'),
    path('userroles/<int:pk>/edit/', views.UserRoleUpdateView.as_view(), name='userrole_update'),
    path('userroles/update/', views.update_user_permissions, name='update_user_permissions'),

    # Organization CRUD -> bakviews contains the Organization CBVs kept as bakviews
    path('organizations/', views.OrganizationListView.as_view(), name='organization_list'),
    path('organizations/create/', views.OrganizationCreateView.as_view(), name='organization_create'),
    path('organizations/<int:pk>/', views.OrganizationDetailView.as_view(), name='organization_detail'),
    path('organizations/<int:pk>/edit/', views.OrganizationUpdateView.as_view(), name='organization_update'),
    path('organizations/<int:pk>/delete/', views.OrganizationDeleteView.as_view(), name='organization_delete'),
]
