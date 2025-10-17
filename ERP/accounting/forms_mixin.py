"""
Base form mixin to apply Dason/Bootstrap widget classes.
"""
from django import forms

class BootstrapFormMixin(forms.Form):
    def __init__(self, *args, **kwargs):
        kwargs.pop('organization', None)
        kwargs.pop('voucher_mode', None)
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css_class = field.widget.attrs.get('class', '')
            if 'form-control' not in css_class:
                field.widget.attrs['class'] = (css_class + ' form-control').strip()
