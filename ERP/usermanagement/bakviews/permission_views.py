from django.views.generic import ListView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import redirect
from ..models import UserRole, Role, EntityPermission, Module
from ..forms import UserRoleForm, EntityPermissionForm
from ..mixins import UserOrganizationMixin

# Permission Management Views
class UserPermissionListView(UserOrganizationMixin, ListView):
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

class UserRoleUpdateView(UserOrganizationMixin, UpdateView):
    model = UserRole
    form_class = UserRoleForm
    template_name = 'usermanagement/userrole_form.html'
    success_url = reverse_lazy('usermanagement:permission_list')

    def get_queryset(self):
        return UserRole.objects.filter(organization=self.get_organization())

    def form_valid(self, form):
        messages.success(self.request, 'User role updated successfully.')
        return super().form_valid(form)

class EntityPermissionUpdateView(UserOrganizationMixin, UpdateView):
    model = EntityPermission
    form_class = EntityPermissionForm
    template_name = 'usermanagement/entitypermission_form.html'
    success_url = reverse_lazy('usermanagement:permission_list')

    def get_queryset(self):
        return EntityPermission.objects.filter(organization=self.get_organization())

    def form_valid(self, form):
        messages.success(self.request, 'Entity permission updated successfully.')
        return super().form_valid(form)

def update_user_permissions(request):
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        role_ids = request.POST.getlist('roles')
        
        user = User.objects.get(id=user_id)
        organization = user.organization
        
        # Delete existing roles
        UserRole.objects.filter(user=user, organization=organization).delete()
        
        # Create new roles
        for role_id in role_ids:
            role = Role.objects.get(id=role_id)
            UserRole.objects.create(
                user=user,
                role=role,
                organization=organization
            )
        
        messages.success(request, 'User roles updated successfully.')
        return redirect('usermanagement:permission_list')
    
    return redirect('usermanagement:permission_list') 