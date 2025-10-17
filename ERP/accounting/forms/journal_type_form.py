from django import forms
from accounting.models import JournalType
from accounting.forms_mixin import BootstrapFormMixin

class JournalTypeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = JournalType
        fields = '__all__' 