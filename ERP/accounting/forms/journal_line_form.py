"""
Journal Line Form - ModelForm for JournalLine model.

This form handles individual journal line items including:
- account: Chart of account
- description: Line description
- debit_amount: Debit amount
- credit_amount: Credit amount
+ txn_currency: Transaction currency
+ fx_rate: Exchange rate for multi-currency
- department, project, cost_center: Dimension fields
- tax_code, tax_rate, tax_amount: Tax fields
- memo: Additional notes
- udf_data: User-defined fields

Validation:
- Each line must have EITHER debit OR credit (not both, not neither)
- Amounts must be non-negative
- Tax rate and amount consistency
"""

import logging
from decimal import Decimal
from typing import Optional, Dict

from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _

from accounting.models import Journal, JournalLine, ChartOfAccount, Currency, Department
from accounting.models import Project, CostCenter, TaxCode
from accounting.forms_mixin import BootstrapFormMixin

logger = logging.getLogger(__name__)


class JournalLineForm(BootstrapFormMixin, forms.ModelForm):
    """
    Form for creating/editing individual journal line items.

    Fields:
        - account: Chart of account (required)
        - description: Optional line description
        - debit_amount: Debit amount (non-negative)
        - credit_amount: Credit amount (non-negative)
        - txn_currency: Transaction currency
        - fx_rate: Exchange rate if multi-currency
        - department: Optional dimension
        - project: Optional dimension
        - cost_center: Optional dimension
        - tax_code: Optional tax code
        - tax_rate: Tax rate percentage
        - tax_amount: Calculated tax amount
        - memo: Additional notes

    Special Fields:
        - save_as_default: Boolean to save as default line template

    Validation Rules:
        1. Exactly one of debit_amount or credit_amount must be non-zero
        2. Amounts must be >= 0
        3. Tax rate must be between 0 and 100
        4. Tax amount auto-calculated if needed
    """

    # Additional fields not in model
    save_as_default = forms.BooleanField(
        required=False,
        label=_("Save as default template"),
        help_text=_("Save this line as a template for future entries")
    )

    class Meta:
        model = JournalLine
        fields = [
            'account', 'description', 'debit_amount', 'credit_amount',
            'txn_currency', 'fx_rate', 'department', 'project',
            'cost_center', 'tax_code', 'tax_rate', 'tax_amount', 'memo', 'udf_data'
        ]
        widgets = {
            'account': forms.Select(attrs={
                'class': 'form-select',
                'required': 'required',
                'aria-label': _('Account'),
                'data-allow-clear': 'true'
            }),
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Enter description'),
                'aria-label': _('Description')
            }),
            'debit_amount': forms.NumberInput(attrs={
                'class': 'form-control debit-amount',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00',
                'aria-label': _('Debit Amount'),
                'data-type': 'currency'
            }),
            'credit_amount': forms.NumberInput(attrs={
                'class': 'form-control credit-amount',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00',
                'aria-label': _('Credit Amount'),
                'data-type': 'currency'
            }),
            'txn_currency': forms.Select(attrs={
                'class': 'form-select',
                'aria-label': _('Currency'),
                'data-allow-clear': 'true'
            }),
            'fx_rate': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.000001',
                'min': '0.000001',
                'value': '1.000000',
                'aria-label': _('Exchange Rate')
            }),
            'department': forms.Select(attrs={
                'class': 'form-select',
                'aria-label': _('Department'),
                'data-allow-clear': 'true'
            }),
            'project': forms.Select(attrs={
                'class': 'form-select',
                'aria-label': _('Project'),
                'data-allow-clear': 'true'
            }),
            'cost_center': forms.Select(attrs={
                'class': 'form-select',
                'aria-label': _('Cost Center'),
                'data-allow-clear': 'true'
            }),
            'tax_code': forms.Select(attrs={
                'class': 'form-select',
                'aria-label': _('Tax Code'),
                'data-allow-clear': 'true'
            }),
            'tax_rate': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'max': '100',
                'placeholder': '0.00',
                'aria-label': _('Tax Rate %')
            }),
            'tax_amount': forms.NumberInput(attrs={
                'class': 'form-control tax-amount',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00',
                'aria-label': _('Tax Amount'),
                'readonly': 'readonly'
            }),
            'memo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Optional memo'),
                'aria-label': _('Memo')
            }),
            'udf_data': forms.HiddenInput()
        }

    def __init__(self, *args, **kwargs):
        """
        Initialize the form with organization context.

        Args:
            organization: Organization instance for filtering choices
            journal: Optional parent Journal instance
        """
        self.organization = kwargs.pop('organization', None)
        self.journal = kwargs.pop('journal', None)

        super().__init__(*args, **kwargs)

        # Filter accounts by organization and active status
        if self.organization:
            self.fields['account'].queryset = ChartOfAccount.objects.filter(
                organization=self.organization,
                is_active=True
            ).select_related('account_type')

            # Filter dimensions by organization
            self.fields['department'].queryset = Department.objects.filter(
                organization=self.organization
            )
            self.fields['project'].queryset = Project.objects.filter(
                organization=self.organization,
                is_active=True
            )
            self.fields['cost_center'].queryset = CostCenter.objects.filter(
                organization=self.organization,
                is_active=True
            )
            self.fields['tax_code'].queryset = TaxCode.objects.filter(
                organization=self.organization,
                is_active=True
            )

            # Filter active currencies
            self.fields['txn_currency'].queryset = Currency.objects.filter(
                is_active=True
            )
        else:
            # No organization - return empty querysets
            self.fields['account'].queryset = ChartOfAccount.objects.none()
            self.fields['department'].queryset = Department.objects.none()
            self.fields['project'].queryset = Project.objects.none()
            self.fields['cost_center'].queryset = CostCenter.objects.none()
            self.fields['tax_code'].queryset = TaxCode.objects.none()
            self.fields['txn_currency'].queryset = Currency.objects.none()

        # Set default values
        if not self.instance.pk:
            self.fields['fx_rate'].initial = 1.0
            self.fields['txn_currency'].initial = 'USD'

    def clean_debit_amount(self) -> Optional[Decimal]:
        """
        Validate debit amount is non-negative.

        Returns:
            Decimal: The cleaned debit_amount
        """
        debit = self.cleaned_data.get('debit_amount')

        if debit is None or debit == '':
            return Decimal('0.00')

        if Decimal(str(debit)) < 0:
            raise ValidationError(
                _('Debit amount cannot be negative.'),
                code='negative_debit'
            )

        return Decimal(str(debit))

    def clean_credit_amount(self) -> Optional[Decimal]:
        """
        Validate credit amount is non-negative.

        Returns:
            Decimal: The cleaned credit_amount
        """
        credit = self.cleaned_data.get('credit_amount')

        if credit is None or credit == '':
            return Decimal('0.00')

        if Decimal(str(credit)) < 0:
            raise ValidationError(
                _('Credit amount cannot be negative.'),
                code='negative_credit'
            )

        return Decimal(str(credit))

    def clean_tax_rate(self) -> Optional[Decimal]:
        """
        Validate tax rate is between 0 and 100.

        Returns:
            Decimal: The cleaned tax_rate
        """
        tax_rate = self.cleaned_data.get('tax_rate')

        if tax_rate is None:
            return None

        tax_rate_decimal = Decimal(str(tax_rate))

        if tax_rate_decimal < 0 or tax_rate_decimal > 100:
            raise ValidationError(
                _('Tax rate must be between 0 and 100.'),
                code='invalid_tax_rate'
            )

        return tax_rate_decimal

    def clean_fx_rate(self) -> Optional[Decimal]:
        """
        Validate exchange rate is positive.

        Returns:
            Decimal: The cleaned fx_rate
        """
        exchange_rate = self.cleaned_data.get('fx_rate')

        if exchange_rate is None or exchange_rate == '':
            return Decimal('1.000000')

        if Decimal(str(exchange_rate)) <= 0:
            raise ValidationError(
                _('Exchange rate must be greater than zero.'),
                code='invalid_exchange_rate'
            )

        return Decimal(str(exchange_rate))

    def clean(self) -> Dict:
        """
        Perform comprehensive line-level validation.

        Validation rules:
        1. Exactly ONE of debit or credit must be non-zero
        2. Cannot have both debit and credit
        3. Cannot have both zero
        4. Tax rate and tax code relationship
        5. Dimension consistency

        Raises:
            ValidationError: If validation fails

        Returns:
            dict: The cleaned data
        """
        cleaned_data = super().clean()

        debit = Decimal(str(cleaned_data.get('debit_amount') or 0))
        credit = Decimal(str(cleaned_data.get('credit_amount') or 0))
        tax_rate = cleaned_data.get('tax_rate')
        tax_code = cleaned_data.get('tax_code')

        # Rule 1: Must have either debit OR credit (not both, not neither)
        if debit > 0 and credit > 0:
            raise ValidationError(
                _('A line cannot have both debit and credit amounts.'),
                code='both_debit_credit'
            )

        if debit == 0 and credit == 0:
            raise ValidationError(
                _('A line must have either a debit or credit amount.'),
                code='no_amount'
            )

        # Rule 2: If tax rate specified, validate with tax code
        if tax_rate and tax_rate > 0:
            if not tax_code:
                # Allow tax rate without code, but warn
                logger.warning(
                    f"Tax rate {tax_rate}% specified without tax code in line"
                )

            # Auto-calculate tax amount if we have debit or credit
            amount = debit if debit > 0 else credit
            if amount > 0:
                tax_amount = (amount * Decimal(str(tax_rate))) / Decimal('100')
                cleaned_data['tax_amount'] = tax_amount

        # Rule 3: Account must be specified
        if not cleaned_data.get('account'):
            self.add_error('account', _('Account is required.'))

        return cleaned_data


# Create inline formset for JournalLine
JournalLineFormSet = inlineformset_factory(
    parent_model=Journal,
    model=JournalLine,
    form=JournalLineForm,
    extra=1,  # One blank line for new entries
    can_delete=True,  # Allow deletion of lines
    min_num=1,  # At least one line required
    validate_min=True,
    fields=[
        'account', 'description', 'debit_amount', 'credit_amount',
        'txn_currency', 'fx_rate', 'department', 'project',
        'cost_center', 'tax_code', 'tax_rate', 'tax_amount', 'memo'
    ]
)
