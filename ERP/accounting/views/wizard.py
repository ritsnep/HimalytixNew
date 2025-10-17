from django.forms import Form
from formtools.wizard.views import SessionWizardView
from django.shortcuts import redirect

from accounting.forms import VoucherModeConfigForm as VoucherModeForm
from accounting.forms_factory import FormBuilder
from accounting.services import create_voucher

class VoucherWizardView(SessionWizardView):
    """
    A multi-step wizard for creating vouchers.
    """
    form_list = [
        ('mode', VoucherModeForm),
        ('header', Form),  # Placeholder, will be dynamically generated
        ('lines', Form),   # Placeholder, will be dynamically generated
        ('review', Form),  # Placeholder for the review step
    ]


    def get_template_names(self):
        """
        Returns the template name for the current step.
        """
        return [f'accounting/wizards/steps/{self.steps.current}.html']

    def get_form_class(self, step=None):
        """
        Dynamically generates the form class for the 'header' and 'lines' steps.
        """
        if step is None:
            step = self.steps.current

        # Get the form class from the form_list
        form_class = self.form_list[step]

        # For 'header' and 'lines', we generate the form class on the fly
        if step in ['header', 'lines']:
            mode_data = self.get_cleaned_data_for_step('mode')
            if not mode_data:
                # This can happen if the user navigates directly to a later step
                # We'll redirect them to the first step to select a mode
                # Since we can't redirect from here, we'll return a basic form
                # The view's dispatch logic should handle the redirect.
                return Form

            config = mode_data.get('mode')
            if not config:
                 return Form

            if step == 'header':
                # Build the form class for the header
                form_class = FormBuilder(config.ui_schema.get('header')).build_form()
            elif step == 'lines':
                # Build the formset class for the lines
                form_class = FormBuilder(config.ui_schema.get('lines')).build_formset()
        
        return form_class

    def done(self, form_list, **kwargs):
        """
        Called when the final step is completed.
        
        This method processes the cleaned data from all steps and creates the voucher.
        """
        form_data = self.get_all_cleaned_data()
        
        # Extract data for create_voucher service
        mode_config = form_data.pop('mode')
        header_data = form_data
        lines_data = form_data.pop('lines') # Assuming formset data is under 'lines'

        # Call the service function to create the voucher
        create_voucher(
            mode_config=mode_config,
            header_data=header_data,
            lines_data=lines_data,
            user=self.request.user
        )
        
        # Redirect to a success page or another appropriate view
        return redirect('accounting:voucher_list')