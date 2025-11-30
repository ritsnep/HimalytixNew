from django import forms

from .models import IRDSettings


class IRDSettingsForm(forms.ModelForm):
    class Meta:
        model = IRDSettings
        fields = ["seller_pan", "username", "password"]
        widgets = {
            "password": forms.PasswordInput(render_value=True),
        }
