from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import redirect
from django.contrib.auth import get_user_model
from ..models import UserRole, Role, EntityPermission, Organization, Module
from ..forms import UserRoleForm, EntityPermissionForm
from ..mixins import UserOrganizationMixin, EntityPermissionMixin

User = get_user_model()

# User Management Views
class UserListView(UserOrganizationMixin, ListView):
    model = User
    template_name = 'usermanagement/user_list.html'
    context_object_name = 'users'

    def get_queryset(self):
        return User.objects.filter(organization=self.get_organization())

class UserCreateView(UserOrganizationMixin, CreateView):
    model = User
    template_name = 'usermanagement/user_form.html'
    fields = ['username', 'email', 'full_name', 'is_active']
    success_url = reverse_lazy('usermanagement:user_list')

    def form_valid(self, form):
        form.instance.organization = self.get_organization()
        messages.success(self.request, 'User created successfully.')
        return super().form_valid(form)

class UserDetailView(UserOrganizationMixin, DetailView):
    model = User
    template_name = 'usermanagement/user_detail.html'
    context_object_name = 'user'

    def get_queryset(self):
        return User.objects.filter(organization=self.get_organization())

class UserUpdateView(UserOrganizationMixin, UpdateView):
    model = User
    template_name = 'usermanagement/user_form.html'
    fields = ['username', 'email', 'full_name', 'is_active']
    success_url = reverse_lazy('usermanagement:user_list')

    def get_queryset(self):
        return User.objects.filter(organization=self.get_organization())

    def form_valid(self, form):
        messages.success(self.request, 'User updated successfully.')
        return super().form_valid(form)

class UserDeleteView(UserOrganizationMixin, DeleteView):
    model = User
    template_name = 'usermanagement/user_confirm_delete.html'
    success_url = reverse_lazy('usermanagement:user_list')

    def get_queryset(self):
        return User.objects.filter(organization=self.get_organization())

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'User deleted successfully.')
        return super().delete(request, *args, **kwargs) 