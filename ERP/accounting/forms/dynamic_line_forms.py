from django import forms
from django.core.exceptions import ValidationError
from accounting.services import ValidationService

class GenericVoucherLineForm(forms.Form):
    account_id = forms.IntegerField(required=True)
    debit_amount = forms.DecimalField(max_digits=15, decimal_places=2, required=False)
    credit_amount = forms.DecimalField(max_digits=15, decimal_places=2, required=False)
    description = forms.CharField(max_length=255, required=False)
    quantity = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    unit_price = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    item_id = forms.IntegerField(required=False)
    tax_code_id = forms.IntegerField(required=False)
    cost_center_id = forms.IntegerField(required=False)
    project_id = forms.IntegerField(required=False)
    department_id = forms.IntegerField(required=False)
    
    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        self.config = kwargs.pop('config', None)
        super().__init__(*args, **kwargs)
    
    def clean(self):
        cleaned_data = super().clean()
        
        debit = cleaned_data.get('debit_amount') or 0
        credit = cleaned_data.get('credit_amount') or 0
        
        # Must have either debit or credit, not both
        if debit and credit:
            raise ValidationError('Line cannot have both debit and credit amounts', code='DEBIT_CREDIT_BOTH')
        if not debit and not credit:
            raise ValidationError('Line must have either debit or credit amount', code='DEBIT_CREDIT_MISSING')
        
        # Amounts must be positive
        if debit < 0 or credit < 0:
            raise ValidationError('Amounts must be positive', code='AMOUNT_NEGATIVE')
        
        # Quantity validations for inventory vouchers
        quantity = cleaned_data.get('quantity')
        if self.config and self.config.get('affects_inventory') and quantity is not None and quantity <= 0:
            raise ValidationError('Quantity must be positive for inventory transactions', code='QUANTITY_POSITIVE')
        
        # Unit price validations
        unit_price = cleaned_data.get('unit_price')
        if unit_price is not None and unit_price < 0:
            raise ValidationError('Unit price cannot be negative', code='UNIT_PRICE_NEGATIVE')
        
        return cleaned_data