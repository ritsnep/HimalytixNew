from django import forms
from accounting.models import RecurringJournal, RecurringJournalLine
from accounting.forms_mixin import BootstrapFormMixin
from django.forms import inlineformset_factory

class RecurringJournalForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = RecurringJournal
        fields = '__all__'

class RecurringJournalLineForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = RecurringJournalLine
        fields = '__all__'

RecurringJournalLineFormSet = inlineformset_factory(
    RecurringJournal,
    RecurringJournalLine,
    form=RecurringJournalLineForm,
    extra=1,
    can_delete=True
)