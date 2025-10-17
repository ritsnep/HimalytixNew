from django import forms
from accounting.models import CostCenter
from accounting.forms_mixin import BootstrapFormMixin

class CostCenterForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = CostCenter
        fields = '__all__' 