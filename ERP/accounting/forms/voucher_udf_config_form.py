from django import forms
from accounting.models import VoucherUDFConfig
from accounting.forms_mixin import BootstrapFormMixin

class VoucherUDFConfigForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = VoucherUDFConfig
        fields = '__all__' 