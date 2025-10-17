from django.views.generic import TemplateView
from accounting.models import VoucherModeConfig

class VoucherEntryView(TemplateView):
    template_name = 'accounting/voucher_entry.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        config_id = self.kwargs.get('config_id')
        if config_id:
            config = VoucherModeConfig.objects.get(pk=config_id)
        else:
            config = VoucherModeConfig.objects.filter(
                organization=self.request.user.get_active_organization(),
                is_default=True
            ).first()
        
        context['config'] = config
        context['page_title'] = f"Voucher Entry: {config.name}" if config else "Voucher Entry"
        return context