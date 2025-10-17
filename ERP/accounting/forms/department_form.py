from django import forms
from accounting.models import Department
from accounting.forms_mixin import BootstrapFormMixin

class DepartmentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Department
        fields = '__all__' 