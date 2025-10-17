from django import forms
from accounting.models import AccountType
from accounting.forms_mixin import BootstrapFormMixin

class AccountTypeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AccountType
        fields = '__all__' 