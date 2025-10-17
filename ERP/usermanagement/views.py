# usermanagement/views.py
from uuid import UUID
from django.urls import reverse
from django.utils import timezone
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.views import LoginView
from .models import  Module, Entity, CustomUser, Organization, Role
from .forms import  DasonLoginForm, ModuleForm, EntityForm, CustomUserCreationForm
from django.contrib.auth.decorators import login_required
# accounts/views.py or usermanagement/views.py
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import LoginLog
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Module, Entity, CustomUser, Organization, Role, Permission, UserRole
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
    users = CustomUser.objects.all()
    return render(request, 'usermanagement/user_list.html', {'users': users})

@login_required
def delete_user(request, pk):
    user = get_object_or_404(CustomUser, pk=pk)
    user.delete()
    return redirect('user_list')

@login_required
def select_organization(request):
    if request.method == 'POST':
        org_id = request.POST.get('organization')
        if org_id:
            org = Organization.objects.get(id=org_id)
            request.user.set_active_organization(org)
            return redirect(request.GET.get('next', '/'))
    
    organizations = request.user.userorganization_set.all()
    return render(request, 'usermanagement/select_organization.html', {
        'organizations': organizations
    })

class RoleListView(LoginRequiredMixin, ListView):
    model = Role
    template_name = 'usermanagement/role_list.html'
    context_object_name = 'roles'


class RoleCreateView(LoginRequiredMixin, CreateView):
    model = Role
    form_class = RoleForm
    template_name = 'usermanagement/role_form.html'
    success_url = reverse_lazy('role_list')


class RoleUpdateView(LoginRequiredMixin, UpdateView):
    model = Role
    form_class = RoleForm
    template_name = 'usermanagement/role_form.html'
    success_url = reverse_lazy('role_list')


class PermissionListView(LoginRequiredMixin, ListView):
    model = Permission
    template_name = 'usermanagement/permission_list.html'
    context_object_name = 'permissions'


class PermissionCreateView(LoginRequiredMixin, CreateView):
    model = Permission
    form_class = PermissionForm
    template_name = 'usermanagement/permission_form.html'
    success_url = reverse_lazy('permission_list')


class PermissionUpdateView(LoginRequiredMixin, UpdateView):
    model = Permission
    form_class = PermissionForm
    template_name = 'usermanagement/permission_form.html'
    success_url = reverse_lazy('permission_list')


class UserRoleListView(LoginRequiredMixin, ListView):
    model = UserRole
    template_name = 'usermanagement/userrole_list.html'
    context_object_name = 'userroles'


class UserRoleCreateView(LoginRequiredMixin, CreateView):
    model = UserRole
    form_class = UserRoleForm
    template_name = 'usermanagement/userrole_form.html'
    success_url = reverse_lazy('userrole_list')


class UserRoleUpdateView(LoginRequiredMixin, UpdateView):
    model = UserRole
    form_class = UserRoleForm
    template_name = 'usermanagement/userrole_form.html'
    success_url = reverse_lazy('userrole_list')