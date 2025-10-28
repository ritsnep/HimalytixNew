from django import forms
from django.forms import Form
from formtools.wizard.views import SessionWizardView
from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpResponseRedirect
from collections import OrderedDict

from accounting.forms_factory import FormBuilder
from accounting.services import create_voucher
from accounting.models import VoucherModeConfig


class VoucherModeSelectionForm(forms.Form):
    """First step: choose an active voucher mode configuration."""
    mode = forms.ModelChoiceField(
        queryset=VoucherModeConfig.objects.filter(is_active=True),
        label="Voucher Mode",
        required=True,
        empty_label=None,
        help_text="Select the voucher mode to use for this entry.")

class VoucherWizardView(SessionWizardView):
    """
    A multi-step wizard for creating vouchers.
    """
    # Only include the first step; others will be added dynamically
    form_list = [
        ('mode', VoucherModeSelectionForm),
    ]
    
    template_name = 'accounting/wizards/voucher_wizard.html'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cached_form_list = None

    def get_form_list(self):
        """
        Dynamically build the complete form list based on the selected mode.
        """
        # Return cached form list if available to avoid recursion
        if self._cached_form_list is not None:
            return self._cached_form_list
            
        form_list = OrderedDict([('mode', VoucherModeSelectionForm)])
        
        # Try to get mode data from storage directly to avoid recursion
        try:
            step_data = self.storage.get_step_data('mode')
            if step_data:
                # Extract mode from the stored data
                mode_id = step_data.get('mode-mode')
                if mode_id is not None and mode_id != '':
                    try:
                        config = VoucherModeConfig.objects.get(pk=mode_id, is_active=True)
                        # Get UI schema
                        ui = getattr(config, 'resolve_ui', None)
                        schema = ui() if callable(ui) else (config.ui_schema or {})
                        # Add header form if schema exists
                        if schema.get('header'):
                            header_form = FormBuilder(schema.get('header')).build_form()
                            form_list['header'] = header_form
                        # Add lines form if schema exists
                        if schema.get('lines'):
                            lines_form = FormBuilder(schema.get('lines')).build_form()
                            form_list['lines'] = lines_form
                    except VoucherModeConfig.DoesNotExist:
                        pass
        except (AttributeError, KeyError):
            # Storage not initialized yet or no data
            pass
        
        # Cache the form list
        self._cached_form_list = form_list
        return form_list

    def get_template_names(self):
        """
        Returns the template name for the current step.
        """
        return [f'accounting/wizards/steps/{self.steps.current}.html']

    def get(self, request, *args, **kwargs):
        """
        Handle GET requests and validate step access.
        """
        # After initialization, check if user is trying to skip steps
        if hasattr(self, 'steps') and self.steps.current != 'mode':
            mode_data = self.get_cleaned_data_for_step('mode')
            if not mode_data:
                # User hasn't completed mode step, redirect to it
                self.storage.current_step = 'mode'
                return self.render(self.get_form())
        
        return super().get(request, *args, **kwargs)
    
    def post(self, *args, **kwargs):
        """
        Handle POST requests and clear cache when step changes.
        """
        # Clear cached form list when posting (user might be changing mode)
        self._cached_form_list = None
        return super().post(*args, **kwargs)

    def get_form_class(self, step=None):
        """
        Returns the form class for the given step.
        """
        if step is None:
            step = self.steps.current
        
        # Get the current form list (which may be dynamic)
        form_list = self.get_form_list()
        return form_list.get(step, Form)

    def done(self, form_list, **kwargs):
        """
        Called when the final step is completed.
        
        This method processes the cleaned data from all steps and creates the voucher.
        """
        # Extract data from individual steps to avoid cross-contamination
        mode_step = self.get_cleaned_data_for_step('mode') or {}
        header_data = self.get_cleaned_data_for_step('header') or {}
        lines_data = self.get_cleaned_data_for_step('lines') or []

        # Get the mode config object and extract its PK

        config = mode_step.get('mode') if mode_step else None
        config_id = None
        if config is not None:
            if hasattr(config, 'pk'):
                config_id = config.pk
            elif isinstance(config, int):
                config_id = config
            else:
                try:
                    config_id = int(config)
                except Exception:
                    config_id = None

        if not config or not config_id:
            from django.http import HttpResponse
            return HttpResponse("Voucher mode selection is missing or invalid. Please go back and select a voucher mode.", status=400)

        # Call the service function to create the voucher
        journal = create_voucher(
            user=self.request.user,
            config_id=config_id,
            header_data=header_data,
            lines_data=lines_data
        )
        
        # Redirect to the created journal's detail page if available
        try:
            if journal and getattr(journal, 'pk', None):
                messages.success(self.request, f"Voucher {getattr(journal, 'journal_number', journal.pk)} created successfully.")
                return redirect('accounting:voucher_detail', pk=journal.pk)
        except Exception:
            pass
        # Fallback to voucher list
        messages.success(self.request, "Voucher created successfully.")
        return redirect('accounting:voucher_list')