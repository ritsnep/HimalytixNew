# usermanagement/views.py
from uuid import UUID
from django.urls import reverse
from django.utils import timezone
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.views import LoginView
from .models import  Module, Entity, CustomUser, Organization, Role, UserOrganization
from .forms import  DasonLoginForm, ModuleForm, EntityForm, CustomUserCreationForm
from django.contrib.auth.decorators import login_required
# accounts/views.py or usermanagement/views.py
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import LoginLog
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from .mixins import UserOrganizationMixin
from django.contrib.auth import get_user_model
from .models import Module, Entity, CustomUser, Organization, Role, Permission, UserRole, UserOrganization
from .forms import (
    DasonLoginForm,
    ModuleForm,
    EntityForm,
    CustomUserCreationForm,
    RoleForm,
    PermissionForm,
    UserRoleForm,
)
from django.views.generic import ListView, CreateView, UpdateView
from django.views.generic import DetailView, DeleteView
from django.urls import reverse_lazy



def custom_login(request):
    next_url = request.POST.get('next') or request.GET.get('next') or '/'
    if request.method == 'POST':
        form = DasonLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect(next_url)
    else:
        form = DasonLoginForm(request)
    return render(request, 'account/login.html', {'form': form, 'next': next_url})
@login_required

def logout_view(request):
    """
    Logs out the current user and updates their LoginLog entry.
    """
    custom_session_id = request.session.get('custom_session_id')

    # Try converting to UUID safely
    try:
        session_uuid = UUID(custom_session_id) if custom_session_id else None
    except ValueError:
        session_uuid = None

    if session_uuid:
        login_log = LoginLog.objects.filter(session_id=session_uuid).order_by('-login_datetime').first()

        if login_log:
            logout_time = timezone.now()
            login_log.logout_time = logout_time
            login_log.session_time = logout_time - login_log.login_datetime
            login_log.save(update_fields=["logout_time", "session_time"])

    logout(request)
    return redirect(reverse('account_login'))
# def logout_view(request):
#     currentsession = request.session.get('session_id')

#     login_log = LoginLog.objects.filter(session_id=currentsession).order_by('-login_datetime').first()
#     login_datetime = login_log.login_datetime
#     logout_time = timezone.now()
#     login_log.logout_time = logout_time
#     # Calculate session time
#     login_log.session_time = login_log.logout_time - login_datetime
#     login_log.save()
#     logout(request)
#     return redirect('login')  # Redirect to the login page after logout
# --- User CRUD ---
@login_required
def create_user(request):
    form = CustomUserCreationForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect('user_list')
    return render(request, 'usermanagement/user_form.html', {'form': form})

@login_required
def user_list(request):
    users = CustomUser.objects.select_related(
        'organization',
        'organization__tenant'
    ).prefetch_related(
        'user_roles__role',
        'user_permissions',
        'groups'
    ).all()
    return render(request, 'usermanagement/user_list.html', {'users': users})

@login_required
def delete_user(request, pk):
    user = get_object_or_404(CustomUser, pk=pk)
    user.delete()
    return redirect('user_list')

@login_required
def select_organization(request):
    memberships = (
        UserOrganization.objects.filter(user=request.user, is_active=True)
        .select_related('organization', 'organization__tenant')
        .order_by('organization__name')
    )
    tenant = getattr(request, 'tenant', None)
    if tenant:
        memberships = memberships.filter(organization__tenant=tenant)

    if request.method == 'POST':
        org_id = request.POST.get('organization')
        if not org_id:
            messages.error(request, 'Select an organization to continue.')
        else:
            mapping = memberships.filter(organization_id=org_id).first()
            if mapping:
                request.session['active_organization_id'] = mapping.organization_id
                request.session.modified = True
                return redirect(request.GET.get('next') or request.POST.get('next') or '/')
            messages.error(request, 'You are not a member of that organization.')

    return render(
        request,
        'usermanagement/select_organization.html',
        {'organizations': memberships},
    )

class RoleListView(LoginRequiredMixin, ListView):
    model = Role
    template_name = 'usermanagement/role_list.html'
    context_object_name = 'roles'


class RoleCreateView(LoginRequiredMixin, CreateView):
    model = Role
    form_class = RoleForm
    template_name = 'usermanagement/role_form.html'
    success_url = reverse_lazy('usermanagement:role_list')


class RoleUpdateView(LoginRequiredMixin, UpdateView):
    model = Role
    form_class = RoleForm
    template_name = 'usermanagement/role_form.html'
    success_url = reverse_lazy('usermanagement:role_list')


class RoleDetailView(UserOrganizationMixin, DetailView):
    model = Role
    template_name = 'usermanagement/role_detail.html'
    context_object_name = 'role'

    def get_queryset(self):
        # Limit roles to the current organization if applicable
        if self.request.user.is_superuser:
            return Role.objects.all()
        return Role.objects.filter(organization=self.get_organization())


class RoleDeleteView(UserOrganizationMixin, DeleteView):
    model = Role
    template_name = 'usermanagement/role_confirm_delete.html'
    success_url = reverse_lazy('usermanagement:role_list')

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Role.objects.all()
        return Role.objects.filter(organization=self.get_organization())

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Role deleted successfully.')
        return super().delete(request, *args, **kwargs)


class PermissionListView(LoginRequiredMixin, ListView):
    model = Permission
    template_name = 'usermanagement/permission_list.html'
    context_object_name = 'permissions'


class PermissionCreateView(LoginRequiredMixin, CreateView):
    model = Permission
    form_class = PermissionForm
    template_name = 'usermanagement/permission_form.html'
    success_url = reverse_lazy('usermanagement:permission_list')


class PermissionUpdateView(LoginRequiredMixin, UpdateView):
    model = Permission
    form_class = PermissionForm
    template_name = 'usermanagement/permission_form.html'
    success_url = reverse_lazy('usermanagement:permission_list')


class UserRoleListView(LoginRequiredMixin, ListView):
    model = UserRole
    template_name = 'usermanagement/userrole_list.html'
    context_object_name = 'userroles'


class UserRoleCreateView(LoginRequiredMixin, CreateView):
    model = UserRole
    form_class = UserRoleForm
    template_name = 'usermanagement/userrole_form.html'
    success_url = reverse_lazy('usermanagement:userrole_list')


class UserRoleUpdateView(LoginRequiredMixin, UpdateView):
    model = UserRole
    form_class = UserRoleForm
    template_name = 'usermanagement/userrole_form.html'
    success_url = reverse_lazy('usermanagement:userrole_list')


class UserListView(UserOrganizationMixin, ListView):
    model = CustomUser
    template_name = 'usermanagement/user_list.html'
    context_object_name = 'users'

    def get_queryset(self):
        return CustomUser.objects.filter(organization=self.get_organization())


class UserCreateView(UserOrganizationMixin, CreateView):
    model = CustomUser
    template_name = 'usermanagement/user_form.html'
    fields = ['username', 'email', 'full_name', 'is_active']
    success_url = reverse_lazy('usermanagement:user_list')

    def form_valid(self, form):
        form.instance.organization = self.get_organization()
        messages.success(self.request, 'User created successfully.')
        return super().form_valid(form)


class UserDetailView(UserOrganizationMixin, DetailView):
    model = CustomUser
    template_name = 'usermanagement/user_detail.html'
    context_object_name = 'user'

    def get_queryset(self):
        return CustomUser.objects.filter(organization=self.get_organization())


class UserUpdateView(UserOrganizationMixin, UpdateView):
    model = CustomUser
    template_name = 'usermanagement/user_form.html'
    fields = ['username', 'email', 'full_name', 'is_active']
    success_url = reverse_lazy('usermanagement:user_list')

    def get_queryset(self):
        return CustomUser.objects.filter(organization=self.get_organization())

    def form_valid(self, form):
        messages.success(self.request, 'User updated successfully.')
        return super().form_valid(form)


class UserDeleteView(UserOrganizationMixin, DeleteView):
    model = CustomUser
    template_name = 'usermanagement/user_confirm_delete.html'
    success_url = reverse_lazy('usermanagement:user_list')

    def get_queryset(self):
        return CustomUser.objects.filter(organization=self.get_organization())

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'User deleted successfully.')
        return super().delete(request, *args, **kwargs)


class OrganizationListView(UserOrganizationMixin, ListView):
    model = Organization
    template_name = 'usermanagement/organization_list.html'
    context_object_name = 'organizations'

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Organization.objects.all()
        return Organization.objects.filter(id=self.get_organization().id)


class OrganizationCreateView(UserOrganizationMixin, CreateView):
    model = Organization
    template_name = 'usermanagement/organization_form.html'
    fields = ['name', 'code', 'is_active']
    success_url = reverse_lazy('usermanagement:organization_list')

    def form_valid(self, form):
        messages.success(self.request, 'Organization created successfully.')
        return super().form_valid(form)


class OrganizationDetailView(UserOrganizationMixin, DetailView):
    model = Organization
    template_name = 'usermanagement/organization_detail.html'
    context_object_name = 'organization'

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Organization.objects.all()
        return Organization.objects.filter(id=self.get_organization().id)


class OrganizationUpdateView(UserOrganizationMixin, UpdateView):
    model = Organization
    template_name = 'usermanagement/organization_form.html'
    fields = ['name', 'code', 'is_active']
    success_url = reverse_lazy('usermanagement:organization_list')

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Organization.objects.all()
        return Organization.objects.filter(id=self.get_organization().id)

    def form_valid(self, form):
        messages.success(self.request, 'Organization updated successfully.')
        return super().form_valid(form)


class OrganizationDeleteView(UserOrganizationMixin, DeleteView):
    model = Organization
    template_name = 'usermanagement/organization_confirm_delete.html'
    success_url = reverse_lazy('usermanagement:organization_list')

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Organization.objects.all()
        return Organization.objects.filter(id=self.get_organization().id)

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Organization deleted successfully.')
        return super().delete(request, *args, **kwargs)


class UserPermissionListView(UserOrganizationMixin, ListView):
    """Lists user roles and provides access to module/entity permissions per role.

    This view is used as the main 'Permissions' management page displaying user-role
    mappings and entity permissions across modules for the active organization.
    """
    model = UserRole
    template_name = 'usermanagement/user_permissions.html'
    context_object_name = 'user_roles'

    def get_queryset(self):
        return UserRole.objects.filter(organization=self.get_organization())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['roles'] = Role.objects.filter(is_active=True)
        context['active_modules'] = Module.objects.filter(is_active=True)
        return context


@login_required
def update_user_permissions(request):
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        role_ids = request.POST.getlist('roles')
        User = get_user_model()
        user = User.objects.get(id=user_id)
        organization = user.organization

        # Delete existing roles for this user/organization
        UserRole.objects.filter(user=user, organization=organization).delete()

        # Create new user role mappings
        for role_id in role_ids:
            role = Role.objects.get(id=role_id)
            UserRole.objects.create(user=user, role=role, organization=organization)

        messages.success(request, 'User roles updated successfully.')
        return redirect('usermanagement:permission_list')
    return redirect('usermanagement:permission_list')


@login_required
def entity_permission_update(request, entity_id, role_id):
    """Update permissions for a role and entity by toggling Permission presence in role.permissions M2M."""
    role = get_object_or_404(Role, pk=role_id)
    entity = get_object_or_404(Entity, pk=entity_id)
    organization = getattr(request.user, 'organization', None) or request.user.get_active_organization()
    if role.organization != organization:
        messages.error(request, 'Role does not belong to your active organization.')
        return redirect('usermanagement:permission_list')

    if not request.user.has_perm('usermanagement.change_permission'):
        return HttpResponseForbidden()

    if request.method == 'POST':
        actions = request.POST.getlist('actions')
        all_actions = ['view', 'create', 'edit', 'delete']
        for action in all_actions:
            perm, created = Permission.objects.get_or_create(
                module=entity.module,
                entity=entity,
                action=action,
                defaults={'name': f"{entity.name} {action}", 'is_active': False},
            )
            if action in actions:
                role.permissions.add(perm)
            else:
                role.permissions.remove(perm)
        messages.success(request, 'Entity permissions updated successfully.')
    return redirect('usermanagement:permission_list')
