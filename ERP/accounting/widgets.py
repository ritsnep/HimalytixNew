from django import forms

class DatePicker(forms.DateInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attrs.update({'class': 'form-control flatpickr-input', 'data-toggle': 'flatpickr'})

class AccountChoiceWidget(forms.Select):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attrs.update({'class': 'form-control select2', 'data-toggle': 'select2'})