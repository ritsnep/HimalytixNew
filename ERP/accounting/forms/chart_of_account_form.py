from django import forms
from accounting.models import ChartOfAccount, AccountType, Currency
from accounting.forms_mixin import BootstrapFormMixin


class ChartOfAccountForm(BootstrapFormMixin, forms.ModelForm):
    """
    Lightweight tenant-aware COA form used by create/update views.
    Mirrors the enhanced form fields expected by the HTMX template.
    """

    organization = forms.CharField(widget=forms.HiddenInput(), required=False)
    account_code = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'readonly': True,
            'maxlength': '50',
            'pattern': r'^[0-9]+(\.[0-9]{2})*$',
            'title': 'Account code must be numeric, optionally with dot and two digits for children.',
            'placeholder': 'Auto-generated'
        })
    )
    use_custom_code = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'title': 'Check to enter a custom account code.'})
    )
    custom_code = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'maxlength': '50',
            'pattern': r'^[0-9]+(\.[0-9]{2})*$',
            'placeholder': 'Custom Code',
            'title': 'Custom code (numeric; children as \'..NN\')'
        })
    )

    class Meta:
        model = ChartOfAccount
        fields = '__all__'
        widgets = {
            'account_name': forms.TextInput(attrs={'class': 'form-control', 'required': True, 'maxlength': '200', 'placeholder': 'Account Name', 'title': 'Enter the account name (max 200 characters).'}),
            'account_type': forms.Select(attrs={'class': 'form-select', 'required': True, 'title': 'Select the account type.'}),
            'parent_account': forms.Select(attrs={'class': 'form-select', 'title': 'Select the parent account if any.'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'maxlength': '500', 'placeholder': 'Description (optional)', 'title': 'Describe the account (optional, max 500 characters).'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input', 'title': 'Is this account active?'}),
            'is_bank_account': forms.CheckboxInput(attrs={'class': 'form-check-input', 'title': 'Is this a bank account?'}),
            'bank_name': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '100', 'placeholder': 'Bank Name', 'title': 'Name of the bank (optional).'}),
            'bank_branch': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '100', 'placeholder': 'Bank Branch', 'title': 'Bank branch (optional).'}),
            'account_number': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '64', 'placeholder': 'Account Number', 'title': 'Bank account number (optional).'}),
            'swift_code': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '11', 'placeholder': 'SWIFT/BIC', 'title': 'SWIFT/BIC code (8 or 11 characters).'}),
            'is_control_account': forms.CheckboxInput(attrs={'class': 'form-check-input', 'title': 'Is this a control account?'}),
            'control_account_type': forms.Select(attrs={'class': 'form-select', 'title': 'Select control account type.'}),
            'require_cost_center': forms.CheckboxInput(attrs={'class': 'form-check-input', 'title': 'Require cost center for transactions?'}),
            'require_project': forms.CheckboxInput(attrs={'class': 'form-check-input', 'title': 'Require project for transactions?'}),
            'require_department': forms.CheckboxInput(attrs={'class': 'form-check-input', 'title': 'Require department for transactions?'}),
            'default_tax_code': forms.Select(attrs={'class': 'form-select', 'title': 'Select default tax code.'}),
            'reconcile': forms.CheckboxInput(attrs={'class': 'form-check-input', 'title': 'Allow reconciliation?'}),
            'currency': forms.Select(attrs={'class': 'form-select', 'title': 'Select the currency.'}),
            'last_reconciled_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'title': 'Last reconciled date.'}),
            'allow_manual_journal': forms.CheckboxInput(attrs={'class': 'form-check-input', 'title': 'Allow manual journal entries?'}),
            'tree_path': forms.HiddenInput(),
            'display_order': forms.NumberInput(attrs={'class': 'form-control', 'value': '0', 'title': 'Display order (optional).'})
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        initial = kwargs.get('initial', {})
        for name, field in self.fields.items():
            if name in initial:
                field.initial = initial[name]

        # System managed numeric fields should not trigger validation errors
        system_hidden_fields = {
            'current_balance': 0.00,
            'reconciled_balance': 0.00,
            'account_level': 1,
        }
        for field_name, default_value in system_hidden_fields.items():
            if field_name in self.fields:
                self.fields[field_name].required = False
                self.fields[field_name].widget = forms.HiddenInput()
                if not self.instance.pk and field_name not in self.initial:
                    self.initial[field_name] = default_value

        opening_balance_field = self.fields.get('opening_balance')
        if opening_balance_field:
            opening_balance_field.required = False
            if not self.instance.pk and 'opening_balance' not in self.initial:
                self.initial['opening_balance'] = 0.00

        # Determine selected account type early for filtering
        selected_account_type = None
        raw_account_type = None
        try:
            raw_account_type = self.data.get('account_type') if hasattr(self, 'data') else None
        except Exception:
            raw_account_type = None
        if raw_account_type not in (None, ''):
            try:
                selected_account_type = int(raw_account_type)
            except (TypeError, ValueError):
                selected_account_type = raw_account_type
        if not selected_account_type:
            selected_account_type = initial.get('account_type') or getattr(self.instance, 'account_type_id', None)

        if self.organization:
            self.fields['organization'].initial = self.organization.pk
            parent_qs = ChartOfAccount.active_accounts.filter(
                organization=self.organization,
                is_active=True,
            )
            self.fields['parent_account'].queryset = parent_qs
            self.fields['account_type'].queryset = AccountType.objects.filter(
                archived_at__isnull=True
            )
            
            # Filter Tax Codes by Organization
            from accounting.models import TaxCode
            self.fields['default_tax_code'].queryset = TaxCode.objects.filter(
                organization=self.organization
            )

            if selected_account_type:
                self.fields['account_type'].initial = selected_account_type
            currency_choices = [(currency.currency_code, f"{currency.currency_code} - {currency.currency_name}")
                               for currency in Currency.objects.filter(is_active=True)]
            self.fields['currency'].widget = forms.Select(attrs={'class': 'form-select'})
            self.fields['currency'].choices = currency_choices
        # Always set organization on the instance for validation
        if self.organization and not getattr(self.instance, 'organization_id', None):
            self.instance.organization = self.organization

        # Set default values for required fields
        if not self.instance.pk:
            self.initial.update({
                'opening_balance': 0.00,
                'current_balance': 0.00,
                'reconciled_balance': 0.00,
                'account_level': 1,
                'is_active': True
            })

        # Generate account code for new instances using backend logic
        if not self.instance.pk:
            org_id = self.organization.pk if self.organization else None
            parent_id = self.data.get('parent_account') or self.initial.get('parent_account')
            account_type_id = self.data.get('account_type') or self.initial.get('account_type')
            if parent_id == '':
                parent_id = None
            if account_type_id == '':
                account_type_id = None
            if org_id and (parent_id or account_type_id):
                generated_code = ChartOfAccount.get_next_code(org_id, parent_id, account_type_id)
                self.initial['account_code'] = generated_code
                self.fields['account_code'].initial = generated_code

    def clean_account_code(self):
        value = (self.cleaned_data.get('account_code') or self.initial.get('account_code', '') or '').strip()
        self.cleaned_data['account_code'] = value
        import re
        if value and not re.match(r'^[0-9]+(\.[0-9]{2})*$', value):
            raise forms.ValidationError('Account code must be numeric, optionally with dot and two digits for children.')
        return value

    def clean_organization(self):
        """
        Keep organization aligned to the active organization; ignore posted string values.
        """
        if self.organization:
            return self.organization
        if getattr(self.instance, 'organization', None):
            return self.instance.organization
        raise forms.ValidationError("Active organization is required to create an account.")

    def clean(self):
        cleaned_data = super().clean()
        parent = cleaned_data.get('parent_account')
        account_type = cleaned_data.get('account_type')

        # Validate account type vs parent
        if parent and account_type and parent.account_type != account_type:
            self.add_error('account_type', "Account type must match the parent account's type.")

        # Circular reference check
        if parent:
            ancestor = parent
            depth = 1
            while ancestor:
                if ancestor == self.instance:
                    self.add_error('parent_account', "Circular parent relationship detected.")
                    break
                ancestor = ancestor.parent_account
                depth += 1
                from django.conf import settings
                if depth > getattr(settings, 'COA_MAX_DEPTH', 10):
                    self.add_error(
                        'parent_account',
                        f"Account tree is too deep (max {getattr(settings, 'COA_MAX_DEPTH', 10)} levels).",
                    )
                    break
        # Suffix overflow check for children
        if parent:
            siblings = ChartOfAccount.active_accounts.filter(
                parent_account=parent,
                organization=self.organization,
            )
            from django.conf import settings
            max_siblings = getattr(settings, 'COA_MAX_SIBLINGS', 99)
            if siblings.count() >= max_siblings:
                self.add_error(
                    'parent_account',
                    f"Maximum number of child accounts ({max_siblings}) reached for this parent.",
                )
        # Set account code if not set
        if not cleaned_data.get('account_code') and not self.instance.pk:
            cleaned_data['account_code'] = self.initial.get('account_code', '')

        # Handle custom code override (account_code doubles as custom entry field)
        use_custom = cleaned_data.get('use_custom_code')
        account_code_value = (cleaned_data.get('account_code') or '').strip()
        cleaned_data['account_code'] = account_code_value
        cleaned_data['custom_code'] = (cleaned_data.get('custom_code') or '').strip()
        if use_custom:
            if not account_code_value:
                self.add_error('account_code', 'Please enter an account code or turn off "Use Custom Code".')
            else:
                # Validate uniqueness inside the organization
                org_id = getattr(self, 'organization', None) and self.organization.id
                if org_id:
                    qs = ChartOfAccount.objects.filter(organization_id=org_id, account_code=account_code_value)
                    if self.instance.pk:
                        qs = qs.exclude(pk=self.instance.pk)
                    if qs.exists():
                        self.add_error('account_code', 'This code already exists in your organization.')
                cleaned_data['custom_code'] = account_code_value
        else:
            cleaned_data['custom_code'] = None

        # Enforce uniqueness for account_code within organization (regardless of custom toggle)
        if account_code_value and self.organization:
            qs = ChartOfAccount.objects.filter(organization=self.organization, account_code=account_code_value)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error('account_code', '[COA_DUPLICATE_CODE] This account code already exists in your organization.')

        # Set default values for required fields if not provided
        if not cleaned_data.get('opening_balance'):
            cleaned_data['opening_balance'] = 0.00
        if not cleaned_data.get('current_balance'):
            cleaned_data['current_balance'] = 0.00
        if not cleaned_data.get('reconciled_balance'):
            cleaned_data['reconciled_balance'] = 0.00
        if not cleaned_data.get('account_level'):
            cleaned_data['account_level'] = 1

        # Conditional validation for bank account details
        is_bank = cleaned_data.get('is_bank_account')
        if is_bank:
            if not cleaned_data.get('account_number'):
                self.add_error('account_number', 'Account number is required for bank accounts.')
            swift = cleaned_data.get('swift_code')
            if swift:
                import re as _re
                if not _re.match(r'^[A-Za-z0-9]{8}([A-Za-z0-9]{3})?$', swift):
                    self.add_error('swift_code', 'SWIFT/BIC must be 8 or 11 alphanumeric characters.')

        # Control account type required when control account enabled
        if cleaned_data.get('is_control_account') and not cleaned_data.get('control_account_type'):
            self.add_error('control_account_type', 'Control account type is required when Control Account is enabled.')

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Set organization for new instances
        if self.organization and not instance.pk:
            instance.organization = self.organization

        # Set account code / custom code mapping
        instance.use_custom_code = self.cleaned_data.get('use_custom_code', False)
        instance.custom_code = (self.cleaned_data.get('custom_code') or '').strip() or None
        if not instance.pk:
            if instance.use_custom_code:
                instance.account_code = self.cleaned_data.get('account_code', '')
            else:
                org_id = self.organization.pk if self.organization else None
                parent_id = self.cleaned_data.get('parent_account').pk if self.cleaned_data.get('parent_account') else None
                account_type_id = self.cleaned_data.get('account_type').pk if self.cleaned_data.get('account_type') else None
                if org_id and (parent_id or account_type_id):
                    instance.account_code = ChartOfAccount.get_next_code(org_id, parent_id, account_type_id)
                else:
                    instance.account_code = self.cleaned_data.get('account_code', '')

        # Set account level based on parent
        if instance.parent_account:
            instance.account_level = instance.parent_account.account_level + 1
        else:
            instance.account_level = 1

        if commit:
            instance.save()
            if instance.parent_account:
                base = instance.parent_account.tree_path or ""
                instance.tree_path = f"{base}/{instance.account_id}" if base else str(instance.account_id)
            else:
                instance.tree_path = str(instance.account_id)
            instance.save(update_fields=["tree_path"])
        return instance
