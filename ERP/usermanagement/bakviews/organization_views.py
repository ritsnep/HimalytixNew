from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from ..models import Organization
from ..mixins import UserOrganizationMixin

# Organization Management Views
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