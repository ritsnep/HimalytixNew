from django.views.generic import ListView
from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin
from accounting.models import VoucherModeConfig
from accounting.forms import VoucherModeConfigForm
from django.urls import reverse, reverse_lazy
from django.contrib import messages

class VoucherModeConfigListView(PermissionRequiredMixin, LoginRequiredMixin, ListView):
    model = VoucherModeConfig
    template_name = 'forms_designer/voucher_config_list_modal.html'
    context_object_name = 'configs'
    permission_required = ('accounting', 'vouchermodeconfig', 'view')
    
    def get_queryset(self):
        return VoucherModeConfig.objects.filter(organization_id=self.request.user.get_active_organization().id)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse('accounting:voucher_config_create')
        context['create_button_text'] = 'New Voucher Mode Config'
        context['page_title'] = 'Voucher Configurations'
        context['breadcrumbs'] = [
            ('Voucher Configurations', None),
        ]
        return context

class VoucherModeConfigUpdateView(PermissionRequiredMixin, LoginRequiredMixin, ListView):
    model = VoucherModeConfig
    form_class = VoucherModeConfigForm
    template_name = 'forms_designer/voucher_config_form.html'
    permission_required = ('accounting', 'vouchermodeconfig', 'change')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = self.request.user.get_active_organization()
        return kwargs
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        form.instance.ui_schema = form.cleaned_data.get('ui_schema')
        messages.success(self.request, "Voucher configuration updated successfully.")
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('accounting:voucher_config_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': f'Update Voucher Configuration: {self.object.name}',
            'page_title': f'Update Voucher Configuration: {self.object.name}',
            'breadcrumbs': [
                ('Voucher Configurations', reverse('accounting:voucher_config_list')),
                (f'Update {self.object.name}', None)
            ]
        })
        return context
