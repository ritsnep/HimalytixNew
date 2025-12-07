from django import forms

from .models import MessageTemplate, NotificationRule


class NotificationRuleForm(forms.ModelForm):
    channels = forms.MultipleChoiceField(
        required=False,
        choices=MessageTemplate.Channel.choices,
        widget=forms.CheckboxSelectMultiple,
        help_text="Leave empty to use the template's default channel.",
    )

    class Meta:
        model = NotificationRule
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial["channels"] = self.instance.channels or []
        elif self.instance and self.instance.template_id:
            self.initial["channels"] = [self.instance.template.channel]

    def clean_channels(self):
        return self.cleaned_data.get("channels") or []
