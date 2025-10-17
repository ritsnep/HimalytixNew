from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from ..models import Role
from ..mixins import UserOrganizationMixin

# Role Management Views
class RoleListView(UserOrganizationMixin, ListView):
    model = Role
    template_name = 'usermanagement/role_list.html'
    context_object_name = 'roles'

    def get_queryset(self):
        return Role.objects.filter(is_active=True)

class RoleCreateView(UserOrganizationMixin, CreateView):
    model = Role
    template_name = 'usermanagement/role_form.html'
    fields = ['name', 'code', 'is_active']
    success_url = reverse_lazy('usermanagement:role_list')

    def form_valid(self, form):
        messages.success(self.request, 'Role created successfully.')
        return super().form_valid(form)

class RoleDetailView(UserOrganizationMixin, DetailView):
    model = Role
    template_name = 'usermanagement/role_detail.html'
    context_object_name = 'role'

class RoleUpdateView(UserOrganizationMixin, UpdateView):
    model = Role
    template_name = 'usermanagement/role_form.html'
    fields = ['name', 'code', 'is_active']
    success_url = reverse_lazy('usermanagement:role_list')

    def form_valid(self, form):
        messages.success(self.request, 'Role updated successfully.')
        return super().form_valid(form)

class RoleDeleteView(UserOrganizationMixin, DeleteView):
    model = Role
    template_name = 'usermanagement/role_confirm_delete.html'
    success_url = reverse_lazy('usermanagement:role_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Role deleted successfully.')
        return super().delete(request, *args, **kwargs) 