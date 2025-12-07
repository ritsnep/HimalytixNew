"""
Base form mixin to apply Dason/Bootstrap widget classes.
"""
from django import forms

from utils.widgets import dual_date_widget, set_default_date_initial

class BootstrapFormMixin(forms.Form):
    def __init__(self, *args, **kwargs):
        organization = kwargs.pop('organization', None)
        kwargs.pop('voucher_mode', None)
        if organization is not None and not getattr(self, "organization", None):
            self.organization = organization
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css_class = field.widget.attrs.get('class', '')
            if 'form-control' not in css_class:
                field.widget.attrs['class'] = (css_class + ' form-control').strip()
        self._apply_dual_calendar_widgets()

    def full_clean(self):
        """Run validation then tag invalid widgets for consistent styling."""
        super().full_clean()
        self._apply_error_classes()

    def _apply_dual_calendar_widgets(self):
        """Normalize all DateFields to the dual AD/BS widget."""
        organization = getattr(self, "organization", None)
        for name, field in self.fields.items():
            if isinstance(field, forms.DateField) and not field.widget.is_hidden:
                attrs = dict(getattr(field.widget, "attrs", {}) or {})
                field.widget = dual_date_widget(attrs=attrs, organization=organization)
                set_default_date_initial(self, name, field)

    def _apply_error_classes(self):
        """Ensure error fields render with Bootstrap's invalid state."""
        if not self.is_bound:
            return

        for name, field in self.fields.items():
            widget = field.widget
            classes = widget.attrs.get('class', '').split()
            if self.errors.get(name):
                if 'is-invalid' not in classes:
                    classes.append('is-invalid')
                widget.attrs['aria-invalid'] = 'true'
            else:
                classes = [cls for cls in classes if cls != 'is-invalid']
                widget.attrs.pop('aria-invalid', None)
            widget.attrs['class'] = ' '.join(classes).strip()
