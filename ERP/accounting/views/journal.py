from django.views import View
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from accounting.models import VoucherModeConfig, JournalLine
from accounting.forms import JournalLineForm
from accounting.views.views import VoucherEntryView  # For schema loading and permission logic
from accounting.forms_factory import build_form  # Assuming this is the schema-driven form builder

class HTMXJournalLineFormView(LoginRequiredMixin, View):
    def get(self, request):
        organization = request.user.get_active_organization()
        form_index = request.GET.get('index', '0')
        config_id = request.GET.get('config_id')
        config = None
        udf_configs = []
        show_dimensions = False
        show_tax_details = False
        form = None
        if config_id:
            config = VoucherModeConfig.objects.filter(pk=config_id).first()
            if config:
                # --- Load schema using the same logic as VoucherEntryView ---
                schema, warning, tried_files = VoucherEntryView().load_schema_for_config(config)
                show_dimensions = getattr(config, 'show_dimensions', False)
                show_tax_details = getattr(config, 'show_tax_details', False)
                udf_configs = list(config.udf_configs.filter(is_active=True, archived_at__isnull=True).order_by('display_order', 'field_name'))
                # --- Build schema-driven line form ---
                if schema and 'lines' in schema:
                    user_perms = VoucherEntryView().get_user_perms(request)
                    LineForm = build_form(schema['lines'], organization=organization, user_perms=user_perms, prefix=f'lines-{form_index}', model=JournalLine)
                    form = LineForm()
        # Fallback to static form if schema/config not found
        if form is None:
            form = JournalLineForm(prefix=f'lines-{form_index}')
        return render(request, 'accounting/partials/journal_line_form.html', {
            'form': form,
            'udf_configs': udf_configs,
            'show_dimensions': show_dimensions,
            'show_tax_details': show_tax_details,
            'config': config,
            'form_index': form_index,
        })
