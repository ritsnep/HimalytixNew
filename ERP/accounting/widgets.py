from django import forms
import logging

logger = logging.getLogger(__name__)

class DatePicker(forms.DateInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attrs.update({'class': 'form-control flatpickr-input', 'data-toggle': 'flatpickr'})

class AccountChoiceWidget(forms.Select):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attrs.update({'class': 'form-control select2', 'data-toggle': 'select2'})

class TypeaheadInput(forms.TextInput):
    """
    Custom TextInput widget that preserves data-* attributes through render().
    This ensures HTMX typeahead fields retain their data-endpoint and other data attributes.
    """
    def render(self, name, value, attrs=None, renderer=None):
        if attrs is None:
            attrs = {}
        
        # Merge self.attrs with provided attrs
        final_attrs = self.build_attrs(self.attrs, attrs)
        
        logger.debug(f"TypeaheadInput.render({name}): final_attrs={final_attrs}")
        
        # Build the HTML manually to ensure data-* attributes are included
        html_attrs = []
        html_attrs.append(f'name="{name}"')
        html_attrs.append('type="text"')
        
        if value:
            html_attrs.append(f'value="{value}"')
        
        for key, val in final_attrs.items():
            if key not in ('name', 'type', 'value') and val is not None and val is not False:
                if val is True:
                    html_attrs.append(key)
                else:
                    html_attrs.append(f'{key}="{val}"')
        
        html_str = f'<input {" ".join(html_attrs)}>'
        
        from django.utils.safestring import mark_safe
        return mark_safe(html_str)