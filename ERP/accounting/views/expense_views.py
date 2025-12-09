from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import FormView

from accounting.forms import ExpenseEntryForm
from accounting.mixins import PermissionRequiredMixin


class ExpenseEntryCreateView(PermissionRequiredMixin, FormView):
    template_name = 'accounting/expenses/expense_entry_form.html'
    form_class = ExpenseEntryForm
    success_url = reverse_lazy('accounting:expense_entry_new')
    permission_required = ('accounting', 'expenseentry', 'add')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Quick Expense Entry'
        context['breadcrumbs'] = [('Expenses', None), ('Quick Entry', None)]
        return context

    def form_valid(self, form):
        expense_entry = form.create_expense_entry(self.request.user)
        journal_number = expense_entry.journal.journal_number
        messages.success(
            self.request,
            f"Expense recorded against {expense_entry.category.name} (Journal {journal_number}).",
        )
        return super().form_valid(form)
*** End of File