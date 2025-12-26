from django import forms
from django.core.exceptions import ValidationError
from datetime import date
from accounting.services import ValidationService

class GenericVoucherHeaderForm(forms.Form):
    voucher_date = forms.DateField(required=True)
    reference_number = forms.CharField(max_length=50, required=False)
    description = forms.CharField(max_length=255, required=True)
    currency_id = forms.IntegerField(required=True)
    exchange_rate = forms.DecimalField(max_digits=10, decimal_places=4, required=False)
    customer_id = forms.IntegerField(required=False)
    vendor_id = forms.IntegerField(required=False)
    project_id = forms.IntegerField(required=False)
    cost_center_id = forms.IntegerField(required=False)
    department_id = forms.IntegerField(required=False)
    
    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        self.module = kwargs.pop('module', None)
        super().__init__(*args, **kwargs)
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Validate voucher date
        voucher_date = cleaned_data.get('voucher_date')
        if voucher_date:
            # Basic date validation - could be extended
            if voucher_date > date.today():
                raise ValidationError('Voucher date cannot be in the future', code='FUTURE_DATE')
        
        # Voucher type specific validations
        if self.module == 'sales' and not cleaned_data.get('customer_id'):
            raise ValidationError('Customer is required for sales vouchers', code='CUSTOMER_REQUIRED')
        
        if self.module == 'purchasing' and not cleaned_data.get('vendor_id'):
            raise ValidationError('Vendor is required for purchase vouchers', code='VENDOR_REQUIRED')
        
        # Date order validations for orders
        if self.module in ['sales', 'purchasing']:
            order_date = cleaned_data.get('order_date')
            delivery_date = cleaned_data.get('delivery_date')
            if order_date and delivery_date and delivery_date < order_date:
                raise ValidationError('Delivery date cannot be before order date', code='DELIVERY_BEFORE_ORDER')
        
        # LC specific validations
        if self.module == 'banking':
            if not cleaned_data.get('bank_id'):
                raise ValidationError('Bank is required for LC vouchers', code='BANK_REQUIRED')
        
        return cleaned_data