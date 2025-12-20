# forms.py
from django import forms
from django.forms import inlineformset_factory
from .models import (
    AccountType,
    Approval,
    Attachment,
    CostCenter,
    Currency,
    Department,
    FiscalYear,
    Journal,
    Journal,
    JournalLine,
    JournalType,
    ChartOfAccount,
    AccountingPeriod,
    Project,
    TaxAuthority,
    TaxCode,
    TaxType,
    VoucherModeConfig,
    VoucherModeDefault,
    CurrencyExchangeRate,
    GeneralLedger,
    VoucherUDFConfig,
    PaymentTerm,
    Vendor,
    Customer,
    Dimension,
    DimensionValue,
    PurchaseInvoice,
    PurchaseInvoiceLine,
    SalesInvoice,
    SalesInvoiceLine,
    SalesOrder,
    SalesOrderLine,
    Quotation,
    QuotationLine,
    ARReceipt,
    ARReceiptLine,
    APPayment,
    APPaymentLine,
    PaymentBatch,
    PaymentApproval,
    BankAccount,
    CashAccount,
    BankTransaction,
    BankStatement,
    BankStatementLine,
    Budget,
    BudgetLine,
    AssetCategory,
    Asset,
    AssetEvent,
    ApprovalWorkflow,
    ApprovalStep,
    ApprovalTask,
    AutoIncrementCodeGenerator,
)
from .forms_mixin import BootstrapFormMixin
import re
import json
from django.utils import timezone

def get_active_currency_choices():
    """Return tuples of active currency codes for select widgets."""
    return [
        (currency.currency_code, f"{currency.currency_code} - {currency.currency_name}")
        for currency in Currency.objects.filter(is_active=True)
    ]


# class FiscalYearForm(forms.ModelForm):
#     class Meta:
#         model = FiscalYear
#         fields = ('code',  'name', 'start_date', 'end_date', 'status', 'is_current')
class FiscalYearForm(BootstrapFormMixin, forms.ModelForm):
    code = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'readonly': True,
        })
    )

    class Meta:
        model = FiscalYear
        fields = ('code', 'name', 'start_date', 'end_date', 'status', 'is_current', 'is_default')
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'data-pristine-required-message': 'Fiscal Year Name is required.',
                'required': 'required',
            }),
            'start_date': forms.TextInput(attrs={
                'class': 'form-control datepicker',
                'data-pristine-required-message': 'Start Date is required.',
                'required': 'required',
                'data-pristine-date-message': 'Please enter a valid date.',
            }),
            'end_date': forms.TextInput(attrs={
                'class': 'form-control datepicker',
                'data-pristine-required-message': 'End Date is required.',
                'required': 'required',
                'data-pristine-date-message': 'Please enter a valid date.',
            }),
            'status': forms.Select(attrs={
                'class': 'form-select',
                'data-pristine-required-message': 'Status is required.',
                'required': 'required',
            }),
            'is_current': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        # Generate code for new instances
        if not self.instance.pk:
            from .models import AutoIncrementCodeGenerator
            code_generator = AutoIncrementCodeGenerator(
                FiscalYear,
                'code',
                organization=self.organization,
                prefix='FY',
                suffix='',
            )
            generated_code = code_generator.generate_code()
            self.initial['code'] = generated_code
            self.fields['code'].initial = generated_code

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date:
            if start_date > end_date:
                self.add_error('end_date', "End Date cannot be before Start Date.")
        return cleaned_data


# New forms below
class AccountingPeriodForm(BootstrapFormMixin, forms.ModelForm):
    fiscal_year = forms.ModelChoiceField(
        queryset=FiscalYear.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=True,
        label="Fiscal Year"
    )
    class Meta:
        model = AccountingPeriod
        fields = ('fiscal_year', 'name', 'period_number', 'start_date', 'end_date', 'status', 'is_current')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'period_number': forms.NumberInput(attrs={'class': 'form-control'}),
            'start_date': forms.TextInput(attrs={'class': 'form-control datepicker'}),
            'end_date': forms.TextInput(attrs={'class': 'form-control datepicker'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'is_current': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        if self.organization:
            self.fields['fiscal_year'].queryset = FiscalYear.objects.filter(organization=self.organization)
        else:
            self.fields['fiscal_year'].queryset = FiscalYear.objects.none()

class DepartmentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Department
        fields = ('code', 'name', 'is_active', 'start_date', 'end_date')
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'start_date': forms.TextInput(attrs={'class': 'form-control datepicker', 'placeholder': 'YYYY-MM-DD'}),
            'end_date': forms.TextInput(attrs={'class': 'form-control datepicker', 'placeholder': 'YYYY-MM-DD'}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        if self.organization:
            self.instance.organization = self.organization
        if not self.instance.pk and not self.initial.get('code'):
            code_generator = AutoIncrementCodeGenerator(
                Department,
                'code',
                organization=self.organization,
                prefix='DEP',
                suffix='',
            )
            generated_code = code_generator.generate_code()
            self.initial['code'] = generated_code
            self.fields['code'].initial = generated_code

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.organization:
            instance.organization = self.organization
        if not instance.code:
            code_generator = AutoIncrementCodeGenerator(
                Department,
                'code',
                organization=self.organization,
                prefix='DEP',
                suffix='',
            )
            instance.code = code_generator.generate_code()
        if commit:
            instance.save()
        return instance

class ProjectForm(BootstrapFormMixin, forms.ModelForm):
    code = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'readonly': True,
        })
    )

    class Meta:
        model = Project
        fields = ('code', 'name', 'description', 'is_active', 'start_date', 'end_date')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'start_date': forms.TextInput(attrs={'class': 'form-control datepicker'}),
            'end_date': forms.TextInput(attrs={'class': 'form-control datepicker'}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)

        # Generate code for new instances
        if not self.instance.pk:
            from .models import AutoIncrementCodeGenerator
            code_generator = AutoIncrementCodeGenerator(
                Project,
                'code',
                organization=self.organization,
                prefix='PRJ',
                suffix='',
            )
            generated_code = code_generator.generate_code()
            self.initial['code'] = generated_code
            self.fields['code'].initial = generated_code

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.organization:
            instance.organization = self.organization
        if commit:
            instance.save()
        return instance

class CostCenterForm(BootstrapFormMixin, forms.ModelForm):
    code = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'readonly': True,
        })
    )

    class Meta:
        model = CostCenter
        fields = ('code', 'name', 'description', 'is_active', 'start_date', 'end_date')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'start_date': forms.TextInput(attrs={'class': 'form-control datepicker'}),
            'end_date': forms.TextInput(attrs={'class': 'form-control datepicker'}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)

        # Generate code for new instances
        if not self.instance.pk:
            from .models import AutoIncrementCodeGenerator
            code_generator = AutoIncrementCodeGenerator(
                CostCenter,
                'code',
                organization=self.organization,
                prefix='CC',
                suffix='',
            )
            generated_code = code_generator.generate_code()
            self.initial['code'] = generated_code
            self.fields['code'].initial = generated_code

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.organization:
            instance.organization = self.organization
        if commit:
            instance.save()
        return instance

# class AccountTypeForm(BootstrapFormMixin, forms.ModelForm):
#     class Meta:
#         model = AccountType
#         fields = ('name', 'nature', 'classification', 'balance_sheet_category',
#                   'income_statement_category', 'display_order', 'system_type')
#         widgets = {
#             'name': forms.TextInput(attrs={'class': 'form-control'}),
#             'nature': forms.Select(attrs={'class': 'form-select'}),
#             'classification': forms.TextInput(attrs={'class': 'form-control'}),
#             'balance_sheet_category': forms.TextInput(attrs={'class': 'form-control'}),
#             'income_statement_category': forms.TextInput(attrs={'class': 'form-control'}),
#             'display_order': forms.NumberInput(attrs={'class': 'form-control'}),
#             'system_type': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
#         }

class AccountTypeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AccountType
        fields = (
            'code',
            'name',
            'nature',
            'classification',
            'balance_sheet_category',
            'income_statement_category',
            'cash_flow_category',
            'display_order',
            'root_code_prefix',
            'root_code_step',
            'system_type',
            'is_archived',
        )
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'nature': forms.Select(attrs={'class': 'form-select'}),
            'classification': forms.TextInput(attrs={'class': 'form-control'}),
            'balance_sheet_category': forms.TextInput(attrs={'class': 'form-control'}),
            'income_statement_category': forms.TextInput(attrs={'class': 'form-control'}),
            'cash_flow_category': forms.TextInput(attrs={'class': 'form-control'}),
            'display_order': forms.NumberInput(attrs={'class': 'form-control'}),
            'root_code_prefix': forms.TextInput(attrs={'class': 'form-control'}),
            'root_code_step': forms.NumberInput(attrs={'class': 'form-control'}),
            'system_type': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_archived': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['root_code_step'].required = False
        if not self.initial.get('root_code_step'):
            self.initial['root_code_step'] = 100
        self.fields['root_code_step'].initial = self.initial['root_code_step']
        self.fields['code'].required = False
        self.fields['code'].widget.attrs['readonly'] = True

class ChartOfAccountForm(BootstrapFormMixin, forms.ModelForm):
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
    opening_balance = forms.DecimalField(
        required=True,
        initial=0.00,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'value': '0.00',
            'step': '0.01',
            'min': '0',
            'max': '999999999999.9999',
            'title': 'Opening balance must be a positive number.'
        })
    )
    current_balance = forms.DecimalField(
        required=True,
        initial=0.00,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'value': '0.00',
            'step': '0.01',
            'min': '-999999999999.9999',
            'max': '999999999999.9999',
            'title': 'Current balance can be negative or positive.'
        })
    )
    reconciled_balance = forms.DecimalField(
        required=True,
        initial=0.00,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'value': '0.00',
            'step': '0.01',
            'min': '-999999999999.9999',
            'max': '999999999999.9999',
            'title': 'Reconciled balance can be negative or positive.'
        })
    )
    account_level = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '10', 'title': 'Account level (1-10)'})
    )

    class Meta:
        model = ChartOfAccount
        fields = [
            'parent_account',
            'account_type',
            'account_code',
            'use_custom_code',
            'custom_code',
            'account_name',
            'description',
            'is_active',
            'is_bank_account',
            'bank_name',
            'bank_branch',
            'account_number',
            'swift_code',
            'is_control_account',
            'control_account_type',
            'require_cost_center',
            'require_project',
            'require_department',
            'default_tax_code',
            'currency',
            'opening_balance',
            'current_balance',
            'reconciled_balance',
            'last_reconciled_date',
            'allow_manual_journal',
            'account_level',
            'tree_path',
            'display_order'
        ]
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
            'control_account_type': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '50', 'placeholder': 'Control Account Type', 'title': 'Type of control account (optional, max 50 characters).'}),
            'require_cost_center': forms.CheckboxInput(attrs={'class': 'form-check-input', 'title': 'Require cost center for transactions?'}),
            'require_project': forms.CheckboxInput(attrs={'class': 'form-check-input', 'title': 'Require project for transactions?'}),
            'require_department': forms.CheckboxInput(attrs={'class': 'form-check-input', 'title': 'Require department for transactions?'}),
            'default_tax_code': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '50', 'placeholder': 'Default Tax Code', 'title': 'Default tax code (optional, max 50 characters).'}),
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
            if selected_account_type:
                self.fields['account_type'].initial = selected_account_type
            currency_choices = [(currency.currency_code, f"{currency.currency_code} - {currency.currency_name}")
                               for currency in Currency.objects.filter(is_active=True)]
            self.fields['currency'].widget = forms.Select(attrs={'class': 'form-select'})
            self.fields['currency'].choices = currency_choices
            # Default to organization's base currency when available
            try:
                base_cur = getattr(self.organization, 'base_currency_code', None)
            except Exception:
                base_cur = None
            if base_cur:
                # Prefer a PK string (currency_code) as the initial rather than
                # a Currency instance, which keeps form.initial consistent.
                if hasattr(base_cur, 'currency_code'):
                    self.fields['currency'].initial = base_cur.currency_code
                else:
                    self.fields['currency'].initial = base_cur
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
            # Require account_number when flagged as bank account
            if not cleaned_data.get('account_number'):
                self.add_error('account_number', 'Account number is required for bank accounts.')
            # Optional: Validate SWIFT/BIC pattern if provided
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

        # Extract and save UDF fields from cleaned_data
        udf_data = {}
        for field_name in list(self.cleaned_data.keys()):
            if field_name.startswith('udf_'):
                udf_key = field_name.replace('udf_', '')
                udf_data[udf_key] = self.cleaned_data[field_name]
        
        if udf_data:
            instance.udf_data = udf_data

        # Set account code / custom code mapping
        instance.use_custom_code = self.cleaned_data.get('use_custom_code', False)
        instance.custom_code = (self.cleaned_data.get('custom_code') or '').strip() or None
        if not instance.pk:
            if instance.use_custom_code:
                instance.account_code = self.cleaned_data.get('account_code', '')
            else:
                # Ensure server-side generation for safety
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

        # # Set tree path
        # if instance.parent_account:
        #     instance.tree_path = f"{instance.parent_account.tree_path}/{instance.account_id}" if instance.parent_account.tree_path else str(instance.account_id)
        # else:
        #     instance.tree_path = str(instance.account_id)

        if commit:
            instance.save()
             # Compute tree path after the instance has an account_id
            if instance.parent_account:
                base = instance.parent_account.tree_path or ""
                instance.tree_path = f"{base}/{instance.account_id}" if base else str(instance.account_id)
            else:
                instance.tree_path = str(instance.account_id)
            instance.save(update_fields=["tree_path"])
        return instance

class CurrencyForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Currency
        fields = ('currency_code', 'currency_name', 'symbol', 'is_active')
        widgets = {
            'currency_code': forms.TextInput(attrs={
                'class': 'form-control',
                'maxlength': '3',
                'style': 'text-transform: uppercase;'
            }),
            'currency_name': forms.TextInput(attrs={'class': 'form-control'}),
            'symbol': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_currency_code(self):
        code = self.cleaned_data['currency_code']
        return code.upper()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:  # If editing existing currency
            self.fields['currency_code'].widget.attrs['readonly'] = True

class CurrencyExchangeRateForm(BootstrapFormMixin, forms.ModelForm):
    from_currency = forms.ModelChoiceField(
        queryset=Currency.objects.filter(is_active=True),
        empty_label="Select From Currency",
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': 'required',
            'data-pristine-required-message': "Please select a 'from' currency."
        })
    )
    to_currency = forms.ModelChoiceField(
        queryset=Currency.objects.filter(is_active=True),
        empty_label="Select To Currency",
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': 'required',
            'data-pristine-required-message': "Please select a 'to' currency."
        })
    )
    rate_date = forms.DateField(
        
        widget=forms.DateInput(attrs={
            'class': 'form-control datepicker',
            'required': 'required',
            'data-pristine-required-message': "Please select a rate date."
        })
    )
    exchange_rate = forms.DecimalField(
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'required': 'required',
            'data-pristine-required-message': "Please enter an exchange rate.",
            'step': '0.000001'
        })
    )
    is_average_rate = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    source = forms.ChoiceField(
        choices=[('manual', 'Manual'), ('api', 'API')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = CurrencyExchangeRate
        fields = ['from_currency', 'to_currency', 'rate_date', 'exchange_rate', 'is_average_rate', 'source']

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        if self.organization:
            self.fields['from_currency'].queryset = Currency.objects.filter(is_active=True)
            self.fields['to_currency'].queryset = Currency.objects.filter(is_active=True)

    def clean(self):
        cleaned_data = super().clean()
        from_currency = cleaned_data.get('from_currency')
        to_currency = cleaned_data.get('to_currency')
        rate_date = cleaned_data.get('rate_date')

        if from_currency and to_currency and rate_date:
            if from_currency == to_currency:
                raise forms.ValidationError("From and To currencies cannot be the same.")

            # Check for duplicate exchange rate
            if CurrencyExchangeRate.objects.filter(
                organization=self.organization,
                from_currency=from_currency,
                to_currency=to_currency,
                rate_date=rate_date
            ).exclude(pk=self.instance.pk if self.instance else None).exists():
                raise forms.ValidationError("An exchange rate for this currency pair and date already exists.")

        return cleaned_data

class JournalTypeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = JournalType
        fields = (
            'code',
            'name',
            'description',
            'auto_numbering_prefix',
            'auto_numbering_suffix',
            'auto_numbering_next',
            'is_system_type',
            'requires_approval',
            'is_active',
        )
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'maxlength': '20',
                'pattern': '^[A-Z0-9_-]+$',
                'title': 'Code must contain only uppercase letters, numbers, hyphens, and underscores'
            }),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'auto_numbering_prefix': forms.TextInput(attrs={
                'class': 'form-control',
                'maxlength': '10',
                'placeholder': 'e.g., GJ, CR, CP'
            }),
            'auto_numbering_suffix': forms.TextInput(attrs={
                'class': 'form-control',
                'maxlength': '10',
                'placeholder': 'e.g., -2024'
            }),
            'auto_numbering_next': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'step': '1'
            }),
            'is_system_type': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'requires_approval': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)

        # Set initial auto_numbering_next if creating new
        if not self.instance.pk and not self.initial.get('auto_numbering_next'):
            self.initial['auto_numbering_next'] = 1

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if not code:
            raise forms.ValidationError("Code is required.")

        # Check for valid characters
        if not re.match(r'^[A-Z0-9_-]+$', code):
            raise forms.ValidationError("Code must contain only uppercase letters, numbers, hyphens, and underscores.")

        # Check uniqueness per organization
        if self.organization:
            existing = JournalType.objects.filter(
                organization=self.organization,
                code=code
            )
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                raise forms.ValidationError(f"A journal type with code '{code}' already exists in this organization.")

        return code.upper()

    def clean(self):
        cleaned_data = super().clean()

        # Ensure at least one of prefix or suffix is provided
        prefix = cleaned_data.get('auto_numbering_prefix')
        suffix = cleaned_data.get('auto_numbering_suffix')

        if not prefix and not suffix:
            raise forms.ValidationError("Either auto numbering prefix or suffix must be provided.")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.organization:
            instance.organization = self.organization
        if commit:
            instance.save()
        return instance

    def get_next_journal_number(self):
        """Generate the next journal number for this journal type"""
        if not self.instance.pk:
            return None

        prefix = self.instance.auto_numbering_prefix or ''
        suffix = self.instance.auto_numbering_suffix or ''
        next_num = self.instance.auto_numbering_next

        # Format the number with leading zeros (e.g., 0001, 0002)
        formatted_num = f"{next_num:04d}"

        journal_number = f"{prefix}{formatted_num}{suffix}"

        # Increment the next number
        self.instance.auto_numbering_next += 1
        self.instance.save(update_fields=['auto_numbering_next'])

        return journal_number

class TaxAuthorityForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = TaxAuthority
        fields = ('name', 'country_code', 'description', 'is_active', 'is_default')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'country_code': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.organization:
            instance.organization = self.organization
        if commit:
            instance.save()
        return instance

class TaxTypeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = TaxType
        fields = ('name', 'authority', 'description', 'filing_frequency', 'is_active')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'authority': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'filing_frequency': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)

        # Filter tax authorities by organization
        if self.organization:
            self.fields['authority'].queryset = TaxAuthority.objects.filter(
                organization=self.organization
            )

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.organization:
            instance.organization = self.organization
        if commit:
            instance.save()
        return instance

class TaxCodeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = TaxCode
        fields = ('name', 'tax_type', 'tax_authority', 'tax_rate', 'rate',
                  'description', 'is_active', 'is_recoverable', 'effective_from')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'tax_type': forms.Select(attrs={'class': 'form-select'}),
            'tax_authority': forms.Select(attrs={'class': 'form-select'}),
            'tax_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_recoverable': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'effective_from': forms.TextInput(attrs={'class': 'form-control datepicker'}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)

        # Filter related models by organization
        if self.organization:
            self.fields['tax_type'].queryset = TaxType.objects.filter(
                organization=self.organization
            )
            self.fields['tax_authority'].queryset = TaxAuthority.objects.filter(
                organization=self.organization
            )

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.organization:
            instance.organization = self.organization
        if commit:
            instance.save()
        return instance

class VoucherModeConfigForm(BootstrapFormMixin, forms.ModelForm):
    currency_warning = None  # Will be set if no currencies

    class Meta:
        model = VoucherModeConfig
        fields = (
            'code', 'name', 'description', 'module', 'journal_type', 'is_default',
            'affects_gl', 'affects_inventory', 'requires_approval',
            'layout_style', 'show_account_balances', 'show_tax_details',
            'show_dimensions', 'allow_multiple_currencies',
            'require_line_description', 'default_currency',
            'default_ledger', 'default_narration_template', 'default_voucher_mode',
            'default_cost_center', 'default_tax_ledger'
        )
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'module': forms.Select(attrs={'class': 'form-select'}),
            'journal_type': forms.Select(attrs={'class': 'form-select'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'affects_gl': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'affects_inventory': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'requires_approval': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'layout_style': forms.Select(attrs={'class': 'form-select'}),
            'show_account_balances': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_tax_details': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_dimensions': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'allow_multiple_currencies': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'require_line_description': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'default_currency': forms.Select(attrs={'class': 'form-select'}),
            'default_ledger': forms.Select(attrs={'class': 'form-select'}),
            'default_narration_template': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'default_voucher_mode': forms.Select(attrs={'class': 'form-select'}),
            'default_cost_center': forms.Select(attrs={'class': 'form-select'}),
            'default_tax_ledger': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)

        # Check if field exists
        if 'default_currency' not in self.fields:
            raise RuntimeError("VoucherModeConfigForm: 'default_currency' field missing from model/form.")

        # Populate currency choices robustly
        currency_choices = [(currency.currency_code, f"{currency.currency_code} - {currency.currency_name}")
                            for currency in Currency.objects.filter(is_active=True)]
        if not currency_choices:
            currency_choices = [('', 'No active currencies available')]
            self.fields['default_currency'].widget.attrs['disabled'] = True
            self.currency_warning = "No active currencies found. Please add currencies in the system settings."
        self.fields['default_currency'].choices = currency_choices

        # Auto-select organization's base currency if available
        try:
            base_cur = getattr(self.organization, 'base_currency_code', None)
        except Exception:
            base_cur = None
        if base_cur:
            if hasattr(base_cur, 'currency_code'):
                self.fields['default_currency'].initial = base_cur.currency_code
            else:
                self.fields['default_currency'].initial = base_cur

        # Fix: use self.organization instead of undefined variable
        if self.organization:
            self.fields['journal_type'].queryset = JournalType.objects.filter(
                organization=self.organization,
                is_active=True
            )
            self.fields['default_ledger'].queryset = ChartOfAccount.active_accounts.filter(
                organization=self.organization,
                is_active=True,
            )
            self.fields['default_cost_center'].queryset = CostCenter.objects.filter(organization=self.organization, is_active=True)
            self.fields['default_tax_ledger'].queryset = ChartOfAccount.active_accounts.filter(
                organization=self.organization,
                is_active=True,
                is_control_account=True,
                control_account_type='tax',
            )
    def get_currency_warning(self):
        return getattr(self, 'currency_warning', None)

    def clean_code(self):
        code = self.cleaned_data.get('code') or ''
        return code.strip()


    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.organization:
            instance.organization = self.organization
        if commit:
            instance.save()
        return instance

class JournalForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Journal
        fields = [
            'journal_type', 'period', 'journal_date', 'reference', 'description', 'currency_code', 'exchange_rate',
            'status'
        ]
        widgets = {
            'journal_type': forms.Select(attrs={'class': 'form-select'}),
            'period': forms.Select(attrs={'class': 'form-select'}),
            'journal_date': forms.DateInput(attrs={
                'class': 'form-control datepicker',
                'required': 'required',
            }),
            'reference': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'currency_code': forms.Select(attrs={'class': 'form-select'}),
            'exchange_rate': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.000001',
                'required': 'required',
            }),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)

        if self.organization:
            self.fields['journal_type'].queryset = JournalType.objects.filter(
                organization=self.organization,
                is_active=True
            )
            self.fields['period'].queryset = AccountingPeriod.objects.filter(
                organization=self.organization,
                status='open'
            )
            self.fields['currency_code'].choices = get_active_currency_choices()
            # Default journal currency to organization's base currency code
            try:
                base_code = getattr(self.organization, 'base_currency_code_id', None)
            except Exception:
                base_code = None
            if base_code:
                self.fields['currency_code'].initial = base_code

    def clean_journal_date(self):
        journal_date = self.cleaned_data.get('journal_date')

        if not hasattr(self, 'organization') or not self.organization:
            # If organization is not set, we cannot perform this validation.
            # The view should be responsible for providing the organization.
            return journal_date

        if journal_date:
            if not AccountingPeriod.is_date_in_open_period(self.organization, journal_date):
                raise forms.ValidationError(
                    "Transaction date must be within an open accounting period."
                )
        return journal_date

    def clean_date(self):
        journal_date = self.cleaned_data['date']
        if self.organization:
            period = AccountingPeriod.objects.filter(
                organization=self.organization,
                start_date__lte=journal_date,
                end_date__gte=journal_date,
                status='open'
            ).first()
            if not period:
                raise forms.ValidationError("Journal date must fall within an open accounting period.")
        return journal_date

class JournalLineForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = JournalLine
        fields = [
            'account', 'description', 'debit_amount', 'credit_amount',
            'currency_code', 'exchange_rate', 'department', 'project', 'cost_center',
            'memo'
        ]
        widgets = {
            'account': forms.Select(attrs={
                'class': 'form-select',
                'required': 'required',
                'data-pristine-required-message': 'Please select an account.'
            }),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'debit_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01', # Allow decimal values
                'data-pristine-required-message': 'Debit amount is required.',
                'data-pristine-min-message': 'Debit amount must be non-negative.',
                'min': '0',
                'data-pristine-number-message': 'Please enter a valid number.'
            }),
            'credit_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01', # Allow decimal values
                'data-pristine-required-message': 'Credit amount is required.',
                'data-pristine-min-message': 'Credit amount must be non-negative.',
                'min': '0',
                'data-pristine-number-message': 'Please enter a valid number.'
            }),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'project': forms.Select(attrs={'class': 'form-select'}),
            'cost_center': forms.Select(attrs={'class': 'form-select'}),
            'memo': forms.TextInput(attrs={'class': 'form-control'}),
            'currency_code': forms.Select(attrs={'class': 'form-select currency-selector'}),
            'exchange_rate': forms.NumberInput(attrs={'class': 'form-control exchange-rate-input', 'step': '0.000001'}),
        }

    def __init__(self, *args, **kwargs):
        organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        if organization:            
            self.fields['account'].queryset = ChartOfAccount.active_accounts.filter(
                organization=organization
            )

            self.fields['department'].queryset = Department.objects.filter(organization=organization)
            self.fields['project'].queryset = Project.objects.filter(organization=organization)
            self.fields['cost_center'].queryset = CostCenter.objects.filter(organization=organization)
            self.fields['tax_code'].queryset = TaxCode.objects.filter(organization=organization) if 'tax_code' in self.fields else TaxCode.objects.none()

            # Populate currency_code choices for JournalLineForm
            currency_choices = [(c.currency_code, f"{c.currency_code} - {c.currency_name}")
                                for c in Currency.objects.filter(is_active=True)]
            if 'currency_code' in self.fields:
                self.fields['currency_code'].choices = [('', '---------')] + currency_choices
                # Default journal line currency to organization's base currency code
                try:
                    base_code = getattr(organization, 'base_currency_code_id', None)
                except Exception:
                    base_code = None
                if base_code:
                    self.fields['currency_code'].initial = base_code

        # Custom validation: ensure either debit or credit is present, but not both or neither.
        # This will be validated server-side.
        self.fields['debit_amount'].required = False # Allow one to be zero if other is non-zero
        self.fields['credit_amount'].required = False # Allow one to be zero if other is non-zero

    def clean(self):
        cleaned_data = super().clean()
        debit = cleaned_data.get('debit_amount')
        credit = cleaned_data.get('credit_amount')

        # Convert None to 0 for consistent comparison
        debit = debit if debit is not None else 0
        credit = credit if credit is not None else 0

        if (debit == 0 and credit == 0) or (debit > 0 and credit > 0):
            # Add error to the form directly
            raise forms.ValidationError(
                "A journal line must have either a Debit amount or a Credit amount, but not both, and not neither."
            )

        account = cleaned_data.get("account")
        if account:
            if account.require_department and not cleaned_data.get("department"):
                self.add_error("department", "Department required for this account.")
            if account.require_project and not cleaned_data.get("project"):
                self.add_error("project", "Project required for this account.")
            if account.require_cost_center and not cleaned_data.get("cost_center"):
                self.add_error("cost_center", "Cost center required for this account.")

        return cleaned_data

# Ensure JournalLineFormSet passes organization to each form
JournalLineFormSet = inlineformset_factory(
    Journal, JournalLine,
    form=JournalLineForm,
    extra=1,
    can_delete=True,
    fields=[
        'account', 'description', 'debit_amount',
        'credit_amount', 'currency_code', 'exchange_rate', 'department', 'project',
        'cost_center', 'memo'
    ]
)

class AttachmentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Attachment
        fields = ['file']

class ApprovalForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Approval
        fields = ['comments']


class VoucherModeDefaultForm(BootstrapFormMixin, forms.ModelForm):
    account_code = forms.CharField(required=False)
    account_type = forms.ModelChoiceField(
        queryset=AccountType.objects.all(),
        required=False,
        empty_label="Select Account Type",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = VoucherModeDefault
        fields = [
            'account', 'account_type', 'default_debit', 'default_credit',
            'default_amount', 'default_tax_code', 'default_department',
            'default_project', 'default_cost_center', 'default_description',
            'is_required', 'display_order'
        ]
        widgets = {
            'account': forms.Select(attrs={'class': 'form-select'}),
            'default_debit': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'default_credit': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'default_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'default_tax_code': forms.Select(attrs={'class': 'form-select'}),
            'default_department': forms.NumberInput(attrs={'class': 'form-control'}),
            'default_project': forms.NumberInput(attrs={'class': 'form-control'}),
            'default_cost_center': forms.NumberInput(attrs={'class': 'form-control'}),
            'default_description': forms.TextInput(attrs={'class': 'form-control'}),
            'is_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'display_order': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        self.voucher_mode = kwargs.pop('voucher_mode', None)
        super().__init__(*args, **kwargs)

        if self.organization:
            self.fields['account'].queryset = ChartOfAccount.active_accounts.filter(
                organization=self.organization,
                is_active=True,
            )
            self.fields['account_type'].queryset = AccountType.objects.filter(
                is_archived=False
            )
            self.fields['default_tax_code'].queryset = TaxCode.objects.filter(
                organization=self.organization,
                is_active=True
            )

    def clean(self):
        cleaned_data = super().clean()
        account = cleaned_data.get('account')
        account_type = cleaned_data.get('account_type')
        default_debit = cleaned_data.get('default_debit')
        default_credit = cleaned_data.get('default_credit')

        # Either account or account_type must be specified
        if not account and not account_type:
            raise forms.ValidationError("Either account or account type must be specified.")

        # Cannot have both debit and credit checked
        if default_debit and default_credit:
            raise forms.ValidationError("Cannot have both debit and credit checked.")

        return cleaned_data

class VoucherUDFConfigForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = VoucherUDFConfig
        fields = [
            'field_name', 'display_name', 'field_type', 'scope', 'is_required',
            'is_active', 'default_value', 'choices', 'min_value', 'max_value',
            'min_length', 'max_length', 'validation_regex', 'help_text', 'display_order'
        ]
        widgets = {
            'field_name': forms.TextInput(attrs={
                'class': 'form-control',
                'maxlength': '50',
                'pattern': '^[a-z][a-z0-9_]*$',
                'title': 'Field name must start with a letter and contain only lowercase letters, numbers, and underscores'
            }),
            'display_name': forms.TextInput(attrs={'class': 'form-control'}),
            'field_type': forms.Select(attrs={'class': 'form-select'}),
            'scope': forms.Select(attrs={'class': 'form-select'}),
            'is_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'default_value': forms.TextInput(attrs={'class': 'form-control'}),
            'choices': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': '3',
                'placeholder': 'Enter choices as JSON array: ["Option 1", "Option 2", "Option 3"]'
            }),
            'min_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'max_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'min_length': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_length': forms.NumberInput(attrs={'class': 'form-control'}),
            'validation_regex': forms.TextInput(attrs={'class': 'form-control'}),
            'help_text': forms.Textarea(attrs={'class': 'form-control', 'rows': '2'}),
            'display_order': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        self.voucher_mode = kwargs.pop('voucher_mode', None)
        super().__init__(*args, **kwargs)

    def clean_field_name(self):
        field_name = self.cleaned_data.get('field_name')
        if not field_name:
            raise forms.ValidationError("Field name is required.")

        # Check for valid characters
        if not re.match(r'^[a-z][a-z0-9_]*$', field_name):
            raise forms.ValidationError("Field name must start with a letter and contain only lowercase letters, numbers, and underscores.")

        # Check uniqueness within the voucher mode
        if self.voucher_mode:
            existing = VoucherUDFConfig.objects.filter(
                voucher_mode=self.voucher_mode,
                field_name=field_name
            )
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                raise forms.ValidationError(f"A field with name '{field_name}' already exists in this voucher mode.")

        return field_name

    def clean_choices(self):
        choices = self.cleaned_data.get('choices')
        field_type = self.cleaned_data.get('field_type')

        if field_type in ['select', 'multiselect'] and not choices:
            raise forms.ValidationError("Choices are required for select and multiselect fields.")

        if choices:
            try:
                import json
                choices_list = json.loads(choices)
                if not isinstance(choices_list, list):
                    raise forms.ValidationError("Choices must be a valid JSON array.")
                if not choices_list:
                    raise forms.ValidationError("Choices array cannot be empty.")
            except json.JSONDecodeError:
                raise forms.ValidationError("Choices must be valid JSON format.")

        return choices

    def clean(self):
        cleaned_data = super().clean()
        field_type = cleaned_data.get('field_type')
        min_value = cleaned_data.get('min_value')
        max_value = cleaned_data.get('max_value')
        min_length = cleaned_data.get('min_length')
        max_length = cleaned_data.get('max_length')

        # Validate numeric constraints
        if field_type in ['number', 'decimal']:
            if min_value is not None and max_value is not None:
                if min_value > max_value:
                    raise forms.ValidationError("Minimum value cannot be greater than maximum value.")

        # Validate length constraints
        if min_length is not None and max_length is not None:
            if min_length > max_length:
                raise forms.ValidationError("Minimum length cannot be greater than maximum length.")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.organization:
            instance.organization = self.organization
        if self.voucher_mode:
            instance.voucher_mode = self.voucher_mode
        if commit:
            instance.save()
        return instance


class PaymentTermForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PaymentTerm
        fields = (
            'code',
            'name',
            'term_type',
            'description',
            'net_due_days',
            'discount_percent',
            'discount_days',
            'is_active',
        )
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'term_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'net_due_days': forms.NumberInput(attrs={'class': 'form-control'}),
            'discount_percent': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'discount_days': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned = super().clean()
        discount_percent = cleaned.get('discount_percent') or 0
        discount_days = cleaned.get('discount_days')
        if discount_percent > 0 and not discount_days:
            self.add_error('discount_days', 'Discount days are required when a discount percent is provided.')
        return cleaned


class VendorForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Vendor
        fields = (
            'code',
            'display_name',
            'legal_name',
            'status',
            'tax_id',
            'payment_term',
            'default_currency',
            'accounts_payable_account',
            'expense_account',
            'email',
            'phone_number',
            'website',
            'credit_limit',
            'on_hold',
            'notes',
            'is_active',
        )
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'display_name': forms.TextInput(attrs={'class': 'form-control'}),
            'legal_name': forms.TextInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'tax_id': forms.TextInput(attrs={'class': 'form-control'}),
            'payment_term': forms.Select(attrs={'class': 'form-select'}),
            'default_currency': forms.Select(attrs={'class': 'form-select'}),
            'accounts_payable_account': forms.Select(attrs={'class': 'form-select'}),
            'expense_account': forms.Select(attrs={'class': 'form-select'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'website': forms.URLInput(attrs={'class': 'form-control'}),
            'credit_limit': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'on_hold': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        if self.organization:
            self.fields['payment_term'].queryset = PaymentTerm.objects.filter(
                organization=self.organization,
            ).filter(term_type__in=['ap', 'both'])
            self.fields['accounts_payable_account'].queryset = ChartOfAccount.objects.filter(
                organization=self.organization,
            )
            self.fields['expense_account'].queryset = ChartOfAccount.objects.filter(
                organization=self.organization,
            )
        # Set default currency queryset and initial
        if 'default_currency' in self.fields:
            self.fields['default_currency'].queryset = Currency.objects.filter(is_active=True)
            try:
                base_cur = getattr(self.organization, 'base_currency_code', None)
            except Exception:
                base_cur = None
            if base_cur:
                if hasattr(base_cur, 'currency_code'):
                    self.fields['default_currency'].initial = base_cur.currency_code
                else:
                    self.fields['default_currency'].initial = base_cur


class CustomerForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Customer
        fields = (
            'code',
            'display_name',
            'legal_name',
            'status',
            'tax_id',
            'payment_term',
            'default_currency',
            'accounts_receivable_account',
            'revenue_account',
            'email',
            'phone_number',
            'website',
            'credit_limit',
            'credit_rating',
            'credit_review_at',
            'on_credit_hold',
            'notes',
            'is_active',
        )
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'display_name': forms.TextInput(attrs={'class': 'form-control'}),
            'legal_name': forms.TextInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'tax_id': forms.TextInput(attrs={'class': 'form-control'}),
            'payment_term': forms.Select(attrs={'class': 'form-select'}),
            'default_currency': forms.Select(attrs={'class': 'form-select'}),
            'accounts_receivable_account': forms.Select(attrs={'class': 'form-select'}),
            'revenue_account': forms.Select(attrs={'class': 'form-select'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'website': forms.URLInput(attrs={'class': 'form-control'}),
            'credit_limit': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'credit_rating': forms.TextInput(attrs={'class': 'form-control'}),
            'credit_review_at': forms.TextInput(attrs={'class': 'form-control datepicker'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'on_credit_hold': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        if self.organization:
            self.fields['payment_term'].queryset = PaymentTerm.objects.filter(
                organization=self.organization,
            ).filter(term_type__in=['ar', 'both'])
            for field_name in ('accounts_receivable_account', 'revenue_account'):
                self.fields[field_name].queryset = ChartOfAccount.objects.filter(
                    organization=self.organization,
                )
        # Set default currency queryset and initial for customer
        if 'default_currency' in self.fields:
            self.fields['default_currency'].queryset = Currency.objects.filter(is_active=True)
            try:
                base_cur = getattr(self.organization, 'base_currency_code', None)
            except Exception:
                base_cur = None
            if base_cur:
                if hasattr(base_cur, 'currency_code'):
                    self.fields['default_currency'].initial = base_cur.currency_code
                else:
                    self.fields['default_currency'].initial = base_cur


class DimensionForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Dimension
        fields = ('code', 'name', 'description', 'dimension_type', 'is_active')
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'dimension_type': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class DimensionValueForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = DimensionValue
        fields = ('dimension', 'code', 'name', 'description', 'is_active')
        widgets = {
            'dimension': forms.Select(attrs={'class': 'form-select'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class SalesInvoiceForm(BootstrapFormMixin, forms.ModelForm):
    # Declare warehouse field manually to avoid circular import at class definition time
    warehouse = forms.ModelChoiceField(
        queryset=None,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='Required when selling inventory items'
    )
    
    class Meta:
        model = SalesInvoice
        fields = (
            'organization',
            'customer',
            'invoice_number',
            'reference_number',
            'invoice_date',
            'due_date',
            'payment_term',
            'currency',
            'exchange_rate',
            'notes',
        )
        widgets = {
            'invoice_number': forms.TextInput(attrs={'class': 'form-control'}),
            'reference_number': forms.TextInput(attrs={'class': 'form-control'}),
            'invoice_date': forms.TextInput(attrs={'class': 'form-control datepicker'}),
            'due_date': forms.TextInput(attrs={'class': 'form-control datepicker'}),
            'payment_term': forms.Select(attrs={'class': 'form-select'}),
            'currency': forms.Select(attrs={'class': 'form-select'}),
            'exchange_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        self.fields['invoice_number'].required = False
        self.fields['invoice_number'].widget.attrs.setdefault('placeholder', 'Auto-generated')
        self.fields['invoice_number'].widget.attrs['readonly'] = True
        if self.organization:
            self.fields['customer'].queryset = self.fields['customer'].queryset.filter(
                organization=self.organization
            )
            # Filter warehouses by organization
            from inventory.models import Warehouse
            self.fields['warehouse'].queryset = Warehouse.objects.filter(
                organization=self.organization, is_active=True
            )
        # Ensure currency queryset and initial default
        if 'currency' in self.fields:
            self.fields['currency'].queryset = Currency.objects.filter(is_active=True)
            try:
                base_cur = getattr(self.organization, 'base_currency_code', None)
            except Exception:
                base_cur = None
            if base_cur:
                if hasattr(base_cur, 'currency_code'):
                    self.fields['currency'].initial = base_cur.currency_code
                else:
                    self.fields['currency'].initial = base_cur

    def clean(self):
        cleaned = super().clean()
        customer = cleaned.get('customer') or getattr(self.instance, 'customer', None)
        payment_term = cleaned.get('payment_term') or getattr(customer, 'payment_term', None)
        invoice_date = cleaned.get('invoice_date')
        due_date = cleaned.get('due_date')
        if invoice_date and not due_date and payment_term:
            cleaned['due_date'] = payment_term.calculate_due_date(invoice_date)
        return cleaned


class SalesInvoiceLineForm(BootstrapFormMixin, forms.ModelForm):
    tax_codes = forms.ModelMultipleChoiceField(
        queryset=TaxCode.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-select tax-multi'}),
        help_text='Select one or more taxes to apply to this line.',
    )

    class Meta:
        model = SalesInvoiceLine
        fields = (
            'description',
            'product_code',
            'quantity',
            'unit_price',
            'discount_amount',
            'revenue_account',
            'tax_code',
            'tax_amount',
            'cost_center',
            'department',
            'project',
            'dimension_value',
        )
        widgets = {
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'product_code': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'discount_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'revenue_account': forms.Select(attrs={'class': 'form-select'}),
            'tax_code': forms.Select(attrs={'class': 'form-select'}),
            'tax_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'cost_center': forms.Select(attrs={'class': 'form-select'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'project': forms.Select(attrs={'class': 'form-select'}),
            'dimension_value': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        self.fields['tax_amount'].widget.attrs.setdefault('readonly', True)
        if self.organization:
            tax_qs = TaxCode.objects.filter(organization=self.organization, is_active=True)
            self.fields['tax_code'].queryset = tax_qs
            self.fields['tax_codes'].queryset = tax_qs
        else:
            self.fields['tax_codes'].queryset = TaxCode.objects.filter(is_active=True)


class QuotationForm(BootstrapFormMixin, forms.ModelForm):
    status = forms.ChoiceField(
        choices=Quotation.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=True,
    )

    class Meta:
        model = Quotation
        fields = (
            'organization',
            'customer',
            'quotation_number',
            'reference_number',
            'quotation_date',
            'valid_until',
            'due_date',
            'payment_term',
            'currency',
            'exchange_rate',
            'status',
            'terms',
            'notes',
        )
        widgets = {
            'quotation_number': forms.TextInput(attrs={'class': 'form-control'}),
            'reference_number': forms.TextInput(attrs={'class': 'form-control'}),
            'quotation_date': forms.TextInput(attrs={'class': 'form-control datepicker'}),
            'valid_until': forms.TextInput(attrs={'class': 'form-control datepicker'}),
            'due_date': forms.TextInput(attrs={'class': 'form-control datepicker'}),
            'payment_term': forms.Select(attrs={'class': 'form-select'}),
            'currency': forms.Select(attrs={'class': 'form-select'}),
            'exchange_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001'}),
            'terms': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        self.fields['quotation_number'].required = False
        self.fields['quotation_number'].widget.attrs.setdefault('placeholder', 'Auto-generated')
        self.fields['quotation_number'].widget.attrs['readonly'] = True
        self.fields['status'].initial = Quotation.STATUS_DRAFT
        if self.organization:
            self.fields['customer'].queryset = self.fields['customer'].queryset.filter(
                organization=self.organization,
            )
        if 'currency' in self.fields:
            self.fields['currency'].queryset = Currency.objects.filter(is_active=True)
            try:
                base_cur = getattr(self.organization, 'base_currency_code', None)
            except Exception:
                base_cur = None
            if base_cur:
                if hasattr(base_cur, 'currency_code'):
                    self.fields['currency'].initial = base_cur.currency_code
                else:
                    self.fields['currency'].initial = base_cur

    def clean(self):
        cleaned = super().clean()
        quotation_date = cleaned.get('quotation_date')
        valid_until = cleaned.get('valid_until')
        payment_term = cleaned.get('payment_term')
        if valid_until and quotation_date and valid_until < quotation_date:
            self.add_error('valid_until', 'Validity date cannot be before the quote date.')
        if quotation_date and not cleaned.get('due_date') and payment_term:
            cleaned['due_date'] = payment_term.calculate_due_date(quotation_date)
        return cleaned


class QuotationLineForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = QuotationLine
        fields = (
            'description',
            'product_code',
            'quantity',
            'unit_price',
            'discount_amount',
            'revenue_account',
            'tax_code',
            'tax_amount',
            'cost_center',
            'department',
            'project',
            'dimension_value',
        )
        widgets = {
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'product_code': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'discount_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'revenue_account': forms.Select(attrs={'class': 'form-select'}),
            'tax_code': forms.Select(attrs={'class': 'form-select'}),
            'tax_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'cost_center': forms.Select(attrs={'class': 'form-select'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'project': forms.Select(attrs={'class': 'form-select'}),
            'dimension_value': forms.Select(attrs={'class': 'form-select'}),
        }


class SalesOrderForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SalesOrder
        fields = (
            'organization',
            'customer',
            'warehouse',
            'order_number',
            'reference_number',
            'order_date',
            'expected_ship_date',
            'currency',
            'exchange_rate',
            'notes',
        )
        widgets = {
            'order_number': forms.TextInput(attrs={'class': 'form-control'}),
            'reference_number': forms.TextInput(attrs={'class': 'form-control'}),
            'order_date': forms.TextInput(attrs={'class': 'form-control datepicker'}),
            'expected_ship_date': forms.TextInput(attrs={'class': 'form-control datepicker'}),
            'warehouse': forms.Select(attrs={'class': 'form-select'}),
            'currency': forms.Select(attrs={'class': 'form-select'}),
            'exchange_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        self.fields['order_number'].required = False
        self.fields['order_number'].widget.attrs.setdefault('placeholder', 'Auto-generated')
        self.fields['order_number'].widget.attrs['readonly'] = True
        if self.organization:
            self.fields['customer'].queryset = self.fields['customer'].queryset.filter(
                organization=self.organization,
            )
            self.fields['warehouse'].queryset = self.fields['warehouse'].queryset.filter(
                organization=self.organization,
            )


class SalesOrderLineForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SalesOrderLine
        fields = (
            'description',
            'product_code',
            'quantity',
            'unit_price',
            'discount_amount',
            'revenue_account',
            'tax_code',
            'tax_amount',
        )
        widgets = {
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'product_code': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'discount_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'revenue_account': forms.Select(attrs={'class': 'form-select'}),
            'tax_code': forms.Select(attrs={'class': 'form-select'}),
            'tax_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

class ARReceiptForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ARReceipt
        fields = (
            'organization',
            'customer',
            'receipt_number',
            'receipt_date',
            'payment_method',
            'reference',
            'currency',
            'exchange_rate',
            'amount',
        )
        widgets = {
            'receipt_number': forms.TextInput(attrs={'class': 'form-control'}),
            'receipt_date': forms.TextInput(attrs={'class': 'form-control datepicker'}),
            'payment_method': forms.TextInput(attrs={'class': 'form-control'}),
            'reference': forms.TextInput(attrs={'class': 'form-control'}),
            'currency': forms.Select(attrs={'class': 'form-select'}),
            'exchange_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        if self.organization:
            self.fields['customer'].queryset = Customer.objects.filter(organization=self.organization)
        self.fields['currency'].queryset = Currency.objects.filter(is_active=True)


class ARReceiptLineForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ARReceiptLine
        fields = ('invoice', 'applied_amount', 'discount_taken')
        widgets = {
            'invoice': forms.Select(attrs={'class': 'form-select'}),
            'applied_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'discount_taken': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        self.customer = kwargs.pop('customer', None)
        super().__init__(*args, **kwargs)
        queryset = SalesInvoice.objects.none()
        if self.organization:
            queryset = SalesInvoice.objects.filter(
                organization=self.organization,
                status__in=['posted'],
            )
        if self.customer:
            queryset = queryset.filter(customer=self.customer)
        self.fields['invoice'].queryset = queryset


class BankAccountForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = BankAccount
        fields = (
            'organization',
            'bank_name',
            'account_name',
            'account_number',
            'account_type',
            'currency',
            'routing_number',
            'swift_code',
            'opening_balance',
            'current_balance',
        )
        widgets = {
            'bank_name': forms.TextInput(attrs={'class': 'form-control'}),
            'account_name': forms.TextInput(attrs={'class': 'form-control'}),
            'account_number': forms.TextInput(attrs={'class': 'form-control'}),
            'account_type': forms.Select(attrs={'class': 'form-select'}),
            'currency': forms.Select(attrs={'class': 'form-select'}),
            'routing_number': forms.TextInput(attrs={'class': 'form-control'}),
            'swift_code': forms.TextInput(attrs={'class': 'form-control'}),
            'opening_balance': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'current_balance': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


class CashAccountForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = CashAccount
        fields = ('organization', 'name', 'currency', 'current_balance', 'location')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'currency': forms.Select(attrs={'class': 'form-select'}),
            'current_balance': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
        }


class BankStatementForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = BankStatement
        fields = ('bank_account', 'period_start', 'period_end', 'status', 'metadata')
        widgets = {
            'bank_account': forms.Select(attrs={'class': 'form-select'}),
            'period_start': forms.TextInput(attrs={'class': 'form-control datepicker'}),
            'period_end': forms.TextInput(attrs={'class': 'form-control datepicker'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'metadata': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class BudgetForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Budget
        fields = ('organization', 'name', 'fiscal_year', 'version', 'status', 'notes')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'fiscal_year': forms.Select(attrs={'class': 'form-select'}),
            'version': forms.TextInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class BudgetLineForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = BudgetLine
        fields = (
            'budget',
            'account',
            'amount_by_month',
            'dimension_value',
            'cost_center',
            'project',
            'department',
        )
        widgets = {
            'budget': forms.Select(attrs={'class': 'form-select'}),
            'account': forms.Select(attrs={'class': 'form-select'}),
            'amount_by_month': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'dimension_value': forms.Select(attrs={'class': 'form-select'}),
            'cost_center': forms.Select(attrs={'class': 'form-select'}),
            'project': forms.Select(attrs={'class': 'form-select'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
        }


class AssetCategoryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AssetCategory
        fields = ('organization', 'name', 'depreciation_expense_account', 'accumulated_depreciation_account')
        widgets = {
            'organization': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'depreciation_expense_account': forms.Select(attrs={'class': 'form-select'}),
            'accumulated_depreciation_account': forms.Select(attrs={'class': 'form-select'}),
        }


class AssetForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Asset
        fields = (
            'organization',
            'name',
            'category',
            'acquisition_date',
            'cost',
            'salvage_value',
            'useful_life_years',
            'depreciation_method',
        )
        widgets = {
            'organization': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'acquisition_date': forms.TextInput(attrs={'class': 'form-control datepicker'}),
            'cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'salvage_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'useful_life_years': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'depreciation_method': forms.Select(attrs={'class': 'form-select'}),
        }


class AssetEventForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AssetEvent
        fields = ('asset', 'event_type', 'event_date', 'description', 'amount')
        widgets = {
            'asset': forms.Select(attrs={'class': 'form-select'}),
            'event_type': forms.Select(attrs={'class': 'form-select'}),
            'event_date': forms.TextInput(attrs={'class': 'form-control datepicker'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


class ApprovalWorkflowForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ApprovalWorkflow
        fields = ('organization', 'name', 'area', 'description', 'active')
        widgets = {
            'organization': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'area': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ApprovalStepForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ApprovalStep
        fields = ('workflow', 'sequence', 'role', 'min_amount')
        widgets = {
            'workflow': forms.Select(attrs={'class': 'form-select'}),
            'sequence': forms.NumberInput(attrs={'class': 'form-control'}),
            'role': forms.TextInput(attrs={'class': 'form-control'}),
            'min_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


class ApprovalTaskForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ApprovalTask
        fields = ('workflow', 'current_step', 'status', 'notes')
        widgets = {
            'workflow': forms.Select(attrs={'class': 'form-select'}),
            'current_step': forms.NumberInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class PaymentBatchForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PaymentBatch
        fields = (
            'organization',
            'batch_number',
            'scheduled_date',
            'currency',
            'status',
            'metadata',
        )
        widgets = {
            'batch_number': forms.TextInput(attrs={'class': 'form-control'}),
            'scheduled_date': forms.TextInput(attrs={'class': 'form-control datepicker'}),
            'currency': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }


class APPaymentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = APPayment
        fields = (
            'organization',
            'vendor',
            'payment_number',
            'payment_date',
            'payment_method',
            'bank_account',
            'currency',
            'exchange_rate',
            'amount',
            'discount_taken',
            'status',
            'batch',
            'metadata',
        )
        widgets = {
            'payment_number': forms.TextInput(attrs={'class': 'form-control'}),
            'payment_date': forms.TextInput(attrs={'class': 'form-control datepicker'}),
            'payment_method': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_account': forms.Select(attrs={'class': 'form-select'}),
            'currency': forms.Select(attrs={'class': 'form-select'}),
            'exchange_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'discount_taken': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'batch': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        if self.organization:
            self.fields['vendor'].queryset = self.fields['vendor'].queryset.filter(
                organization=self.organization
            )
            self.fields['bank_account'].queryset = self.fields['bank_account'].queryset.filter(
                organization=self.organization
            )
            self.instance.organization = self.organization

class APPaymentLineForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = APPaymentLine
        fields = ('invoice', 'applied_amount', 'discount_taken')
        widgets = {
            'invoice': forms.Select(attrs={'class': 'form-select'}),
            'applied_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'discount_taken': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        self.vendor = kwargs.pop('vendor', None)
        super().__init__(*args, **kwargs)

        queryset = PurchaseInvoice.objects.none()
        if self.organization:
            queryset = PurchaseInvoice.objects.filter(organization=self.organization)
        if self.vendor:
            queryset = queryset.filter(vendor=self.vendor)
        self.fields['invoice'].queryset = queryset
