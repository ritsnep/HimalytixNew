app_name = 'usermanagement'
# usermanagement/urls.py
from django.urls import path
from usermanagement import views as main_views
from .view_modules import performance
# bakviews was used for legacy view implementations. All views now live in views.py

urlpatterns = [
    path('users/', main_views.UserListView.as_view(), name='user_list'),
    path('users/create/', main_views.UserCreateView.as_view(), name='user_create'),
    path('users/<int:pk>/', main_views.UserDetailView.as_view(), name='user_detail'),
    path('users/<int:pk>/edit/', main_views.UserUpdateView.as_view(), name='user_update'),
    path('users/<int:pk>/delete/', main_views.UserDeleteView.as_view(), name='user_delete'),
# usermanagement/urls.py
    path('login/', main_views.custom_login, name='login'),
    # path('login/', views.login_view, name='login'),

    path("logout/", main_views.logout_view, name="logout"),
    # path('companies/', views.company_list, name='company_list'),
    # path('companies/create/', views.company_create, name='company_create'),
    # path('companies/edit/<int:pk>/', views.company_edit, name='company_edit'),
    # path('companies/delete/<int:pk>/', views.company_delete, name='company_delete'),
    path('select-organization/', main_views.select_organization, name='select_organization'),


    path('roles/', main_views.RoleListView.as_view(), name='role_list'),
    path('roles/create/', main_views.RoleCreateView.as_view(), name='role_create'),
    path('roles/<int:pk>/edit/', main_views.RoleUpdateView.as_view(), name='role_update'),
    path('roles/<int:pk>/', main_views.RoleDetailView.as_view(), name='role_detail'),
    path('roles/<int:pk>/delete/', main_views.RoleDeleteView.as_view(), name='role_delete'),

    path('permissions/', main_views.UserPermissionListView.as_view(), name='permission_list'),
    path('permissions/create/', main_views.PermissionCreateView.as_view(), name='permission_create'),
    path('permissions/<int:pk>/edit/', main_views.PermissionUpdateView.as_view(), name='permission_update'),
    path('permissions/entity/<int:entity_id>/role/<int:role_id>/update/', main_views.entity_permission_update, name='entity_permission_update'),

    path('userroles/', main_views.UserRoleListView.as_view(), name='userrole_list'),
    path('userroles/create/', main_views.UserRoleCreateView.as_view(), name='userrole_create'),
    path('userroles/<int:pk>/edit/', main_views.UserRoleUpdateView.as_view(), name='userrole_update'),
    path('userroles/update/', main_views.update_user_permissions, name='update_user_permissions'),

    # Organization CRUD -> bakviews contains the Organization CBVs kept as bakviews
    path('organizations/', main_views.OrganizationListView.as_view(), name='organization_list'),
    path('organizations/create/', main_views.OrganizationCreateView.as_view(), name='organization_create'),
    path('organizations/<int:pk>/', main_views.OrganizationDetailView.as_view(), name='organization_detail'),
    path('organizations/<int:pk>/edit/', main_views.OrganizationUpdateView.as_view(), name='organization_update'),
    path('organizations/<int:pk>/delete/', main_views.OrganizationDeleteView.as_view(), name='organization_delete'),

    # Performance monitoring
    path('performance/', performance.permission_performance_dashboard, name='permission_performance'),
    path('performance/api/metrics/', performance.permission_metrics_api, name='permission_metrics_api'),
]