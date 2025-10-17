from django.views.generic import CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404
from django.http import HttpResponse

from accounting.models import Journal, JournalLine
from accounting.forms import JournalForm, JournalLineFormSet

class JournalView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Journal
    form_class = JournalForm
    template_name = 'accounting/vouchers/defaultjournal.html'
    success_url = reverse_lazy('accounting:defaultjournal')
    permission_required = 'accounting.add_journal'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = self.request.user.organization
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['formset'] = JournalLineFormSet(self.request.POST, form_kwargs={'organization': self.request.user.organization})
        else:
            context['formset'] = JournalLineFormSet(form_kwargs={'organization': self.request.user.organization})
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']
        if formset.is_valid():
            self.object = form.save(commit=False)
            self.object.organization = self.request.user.organization
            self.object.created_by = self.request.user
            self.object.save()
            formset.instance = self.object
            formset.save()
            return super().form_valid(form)
        else:
            return self.form_invalid(form)