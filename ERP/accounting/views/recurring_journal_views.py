from django.shortcuts import get_object_or_404, redirect
from django.views.generic import CreateView, ListView, UpdateView, DeleteView
from django.contrib import messages
from django.db import transaction
from accounting.models import Journal, RecurringJournal, RecurringJournalLine
from accounting.forms import RecurringJournalForm, RecurringJournalLineFormSet
from django.urls import reverse_lazy

class RecurringJournalCreateView(CreateView):
    model = RecurringJournal
    form_class = RecurringJournalForm
    template_name = 'accounting/recurring_journal_form.html'
    success_url = reverse_lazy('accounting:recurring-journal-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['formset'] = RecurringJournalLineFormSet(self.request.POST)
        else:
            context['formset'] = RecurringJournalLineFormSet()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']
        with transaction.atomic():
            form.instance.created_by = self.request.user
            self.object = form.save()
            if formset.is_valid():
                formset.instance = self.object
                formset.save()
        messages.success(self.request, "Recurring journal created successfully.")
        return super().form_valid(form)

class RecurringJournalListView(ListView):
    model = RecurringJournal
    template_name = 'accounting/recurring_journal_list.html'
    context_object_name = 'recurring_journals'

class RecurringJournalUpdateView(UpdateView):
    model = RecurringJournal
    form_class = RecurringJournalForm
    template_name = 'accounting/recurring_journal_form.html'
    success_url = reverse_lazy('accounting:recurring-journal-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['formset'] = RecurringJournalLineFormSet(self.request.POST, instance=self.object)
        else:
            context['formset'] = RecurringJournalLineFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']
        with transaction.atomic():
            form.instance.updated_by = self.request.user
            self.object = form.save()
            if formset.is_valid():
                formset.instance = self.object
                formset.save()
        messages.success(self.request, "Recurring journal updated successfully.")
        return super().form_valid(form)

class RecurringJournalDeleteView(DeleteView):
    model = RecurringJournal
    template_name = 'accounting/recurring_journal_confirm_delete.html'
    success_url = reverse_lazy('accounting:recurring-journal-list')