"""Fix Inventory forms to match actual model fields"""

replacements = [
    # PriceListForm - remove price_list_type field
    (
        """class PriceListForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PriceList
        fields = (
            'code', 'name', 'description', 'price_list_type', 'currency_code',
            'valid_from', 'valid_to', 'is_active'
        )
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'price_list_type': forms.Select(attrs={'class': 'form-select'}),
            'currency_code': forms.TextInput(attrs={'class': 'form-control'}),
            'valid_from': forms.DateInput(attrs={'class': 'form-control datepicker'}),
            'valid_to': forms.DateInput(attrs={'class': 'form-control datepicker'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }""",
        """class PriceListForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PriceList
        fields = (
            'code', 'name', 'description', 'currency_code',
            'valid_from', 'valid_to', 'is_active'
        )
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'currency_code': forms.TextInput(attrs={'class': 'form-control'}),
            'valid_from': forms.DateInput(attrs={'class': 'form-control datepicker'}),
            'valid_to': forms.DateInput(attrs={'class': 'form-control datepicker'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }"""
    ),
    # PriceListItemForm - change 'price' to 'unit_price', add discount_percent
    (
        """class PriceListItemForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PriceListItem
        fields = ('product', 'price', 'min_quantity', 'max_quantity')
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'min_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'max_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
        }""",
        """class PriceListItemForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PriceListItem
        fields = ('product', 'unit_price', 'min_quantity', 'max_quantity', 'discount_percent')
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'min_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'max_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'discount_percent': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }"""
    )
]

with open('Inventory/forms.py', 'r', encoding='utf-8') as f:
    content = f.read()

for old, new in replacements:
    if old in content:
        content = content.replace(old, new)
        print(f"Fixed form")
    else:
        print(f"Pattern not found - may already be fixed")

with open('Inventory/forms.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Forms fixed!")
