from django import forms
from django.utils import timezone
from accounting.models import AccountType
from accounting.forms_mixin import BootstrapFormMixin


class AccountTypeForm(BootstrapFormMixin, forms.ModelForm):
    classification = forms.ChoiceField(choices=[], required=True)
    balance_sheet_category = forms.ChoiceField(choices=[], required=False)
    income_statement_category = forms.ChoiceField(choices=[], required=False)
    cash_flow_category = forms.ChoiceField(choices=[], required=False)
    is_archived = forms.BooleanField(required=False)

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['code'].required = False
        self.fields['root_code_step'].required = False
        self.fields['display_order'].required = False
        if not self.initial.get('root_code_step'):
            self.initial['root_code_step'] = self.fields['root_code_step'].initial or 100
        self.fields['root_code_step'].initial = self.initial.get('root_code_step')
        self.fields['is_archived'].initial = bool(getattr(self.instance, 'archived_at', None))

        if not self.is_bound:
            self._apply_default_selections()
            self._apply_code_defaults()
        self._configure_dynamic_choices()

    def _current_value(self, field_name: str):
        if self.data:
            value = self.data.get(field_name)
            if value not in (None, ''):
                return value
        if field_name in self.initial and self.initial[field_name] not in (None, ''):
            return self.initial[field_name]
        return getattr(self.instance, field_name, None)

    def _build_choices(self, enum_cls, options, current_value):
        choices = []
        seen = set()
        for option in options:
            if option in (None, ''):
                continue
            choices.append((option, AccountType._choice_label(enum_cls, option)))
            seen.add(option)
        if current_value and current_value not in seen:
            choices.append((current_value, AccountType._choice_label(enum_cls, current_value)))
        return choices

    def _apply_default_selections(self):
        nature = self._current_value('nature')
        classification = self._current_value('classification')
        if not nature:
            return
        defaults = AccountType.get_default_categories(nature, classification)
        if not classification and defaults.get('classification'):
            classification = defaults['classification']
            self.initial['classification'] = classification
            self.fields['classification'].initial = classification
            defaults = AccountType.get_default_categories(nature, classification)

        for field_name, key in (
            ('balance_sheet_category', 'balance_sheet'),
            ('income_statement_category', 'income_statement'),
            ('cash_flow_category', 'cash_flow'),
        ):
            existing_value = self._current_value(field_name)
            if not existing_value and defaults.get(key):
                self.initial[field_name] = defaults[key]
                self.fields[field_name].initial = defaults[key]

    def _apply_code_defaults(self):
        nature = self._current_value('nature')
        if not self._current_value('root_code_prefix') and nature:
            default_prefix = AccountType.get_default_root_code_prefix(nature)
            self.initial['root_code_prefix'] = default_prefix
            self.fields['root_code_prefix'].initial = default_prefix

        if self._current_value('display_order') in (None, ''):
            next_order = AccountType.next_display_order()
            self.initial['display_order'] = next_order
            self.fields['display_order'].initial = next_order

    def _configure_dynamic_choices(self):
        nature = self._current_value('nature')
        classification_value = self._current_value('classification')
        balance_sheet_value = self._current_value('balance_sheet_category')
        income_statement_value = self._current_value('income_statement_category')
        cash_flow_value = self._current_value('cash_flow_category')

        classification_options = (
            AccountType.CLASSIFICATIONS_BY_NATURE.get(nature)
            or [value for value, _ in AccountType.Classification.choices]
        )

        # Build choices with legacy options separated
        choices = [('', 'Select Classification')]

        # Add current classification options
        for option in classification_options:
            if option in (None, ''):
                continue
            choices.append((option, AccountType._choice_label(AccountType.Classification, option)))

        # Add legacy options separated by a divider
        legacy_options = [
            AccountType.Classification.LEGACY_ASSET,
            AccountType.Classification.LEGACY_LIABILITY,
            AccountType.Classification.LEGACY_EQUITY,
            AccountType.Classification.LEGACY_INCOME,
            AccountType.Classification.LEGACY_EXPENSE,
        ]

        if legacy_options:
            choices.append(('divider', '─' * 20 + ' Legacy Options ' + '─' * 20))
            for option in legacy_options:
                choices.append((option, AccountType._choice_label(AccountType.Classification, option)))

        # Add current value if not already present
        if classification_value and not any(choice[0] == classification_value for choice in choices):
            choices.append((classification_value, AccountType._choice_label(AccountType.Classification, classification_value)))

        self.fields['classification'].choices = choices

        bs_options = AccountType.BALANCE_SHEET_OPTIONS.get(nature)
        if bs_options is None:
            bs_options = AccountType.BALANCE_SHEET_OPTIONS.get('__all__', [])
        self.fields['balance_sheet_category'].choices = [('', 'Select Category')] + self._build_choices(
            AccountType.BalanceSheetCategory,
            bs_options,
            balance_sheet_value,
        )

        is_options = AccountType.INCOME_STATEMENT_OPTIONS.get(nature)
        if is_options is None:
            is_options = AccountType.INCOME_STATEMENT_OPTIONS.get('__all__', [])
        self.fields['income_statement_category'].choices = [('', 'Select Category')] + self._build_choices(
            AccountType.IncomeStatementCategory,
            is_options,
            income_statement_value,
        )

        cash_flow_options = AccountType.CASH_FLOW_OPTIONS
        self.fields['cash_flow_category'].choices = [('', 'Select Category')] + self._build_choices(
            AccountType.CashFlowCategory,
            cash_flow_options,
            cash_flow_value,
        )

    def clean(self):
        cleaned_data = super().clean()
        nature = cleaned_data.get('nature')
        classification = cleaned_data.get('classification')
        defaults = AccountType.get_default_categories(nature, classification)

        if not classification and defaults.get('classification'):
            cleaned_data['classification'] = defaults['classification']
        for field_name, key in (
            ('balance_sheet_category', 'balance_sheet'),
            ('income_statement_category', 'income_statement'),
            ('cash_flow_category', 'cash_flow'),
        ):
            if not cleaned_data.get(field_name) and defaults.get(key):
                cleaned_data[field_name] = defaults[key]

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        is_archived = self.cleaned_data.get('is_archived')
        if is_archived:
            if not instance.archived_at:
                instance.archived_at = timezone.now()
        else:
            instance.archived_at = None
        if commit:
            instance.save()
            self.save_m2m()
        return instance
