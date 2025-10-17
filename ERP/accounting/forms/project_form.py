from django import forms
from accounting.models import Project
from accounting.forms_mixin import BootstrapFormMixin

class ProjectForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Project
        fields = '__all__' 