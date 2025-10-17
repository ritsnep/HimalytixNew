from django import forms
from accounting.models import VoucherModeDefault
from accounting.forms_mixin import BootstrapFormMixin

class VoucherModeDefaultForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = VoucherModeDefault
        fields = '__all__' 