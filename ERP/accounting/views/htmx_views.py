from datetime import timezone
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.views import View
from django.shortcuts import get_object_or_404
from django.forms import formset_factory
from decimal import Decimal

from accounting.models import GeneralLedger, Journal, JournalLine, ChartOfAccount
from accounting.forms import JournalLineForm, JournalForm, JournalLineFormSet
from accounting.forms.form_factory import get_voucher_ui_header
from accounting.models import VoucherModeConfig

class AddJournalRowView(View):
    def post(self, request, *args, **kwargs):
        formset = formset_factory(JournalLineForm, extra=1)
        formset_instance = formset(form_kwargs={'organization': request.user.organization})
        context = {'formset': formset_instance}
        return HttpResponse(render_to_string('accounting/partials/journal_line_form.html', context))

class UpdateTotalsView(View):
    def post(self, request, *args, **kwargs):
        formset = formset_factory(JournalLineForm)
        formset_instance = formset(request.POST, form_kwargs={'organization': request.user.organization})
        total_debit = Decimal('0.00')
        total_credit = Decimal('0.00')
        if formset_instance.is_valid():
            for form in formset_instance:
                if form.cleaned_data:
                    total_debit += form.cleaned_data.get('debit_amount', Decimal('0.00'))
                    total_credit += form.cleaned_data.get('credit_amount', Decimal('0.00'))
        
        imbalance = total_debit - total_credit
        context = {
            'total_debit': total_debit,
            'total_credit': total_credit,
            'imbalance': imbalance,
            'is_balanced': imbalance == Decimal('0.00')
        }
        return HttpResponse(render_to_string('accounting/partials/balance_footer.html', context))

class AutoBalanceView(View):
    def post(self, request, *args, **kwargs):
        formset = formset_factory(JournalLineForm)
        formset_instance = formset(request.POST, form_kwargs={'organization': request.user.organization})
        total_debit = Decimal('0.00')
        total_credit = Decimal('0.00')
        if formset_instance.is_valid():
            for form in formset_instance:
                if form.cleaned_data:
                    total_debit += form.cleaned_data.get('debit_amount', Decimal('0.00'))
                    total_credit += form.cleaned_data.get('credit_amount', Decimal('0.00'))
        
        imbalance = total_debit - total_credit
        if imbalance != Decimal('0.00'):
            # Add a new form to the formset with the balancing amount
            formset_instance.forms.append(formset_instance.empty_form)
            if imbalance > 0:
                formset_instance.forms[-1].initial['credit_amount'] = imbalance
            else:
                formset_instance.forms[-1].initial['debit_amount'] = -imbalance
        
        context = {'formset': formset_instance}
        return HttpResponse(render_to_string('accounting/partials/journal_line_formset.html', context))

class SaveJournalView(View):
    def post(self, request, *args, **kwargs):
        journal_id = kwargs.get('journal_id')
        journal_instance = None
        if journal_id:
            journal_instance = get_object_or_404(Journal, pk=journal_id, organization=request.user.organization)

        header_ui = get_voucher_ui_header(request.user.organization)
        form = JournalForm(request.POST, instance=journal_instance, organization=request.user.organization, ui_schema=header_ui)

        if form.is_valid():
            journal = form.save(commit=False)
            if not journal_id:
                journal.organization = request.user.organization
                journal.created_by = request.user

            # attempt to get line UI schema and pass to formset
            line_ui = None
            try:
                cfg = VoucherModeConfig.objects.filter(organization=request.user.organization, is_default=True).first()
                if cfg:
                    line_ui = cfg.resolve_ui().get('lines')
            except Exception:
                line_ui = None
            line_kwargs = {'organization': request.user.organization}
            if line_ui:
                line_kwargs['ui_schema'] = line_ui
            formset = JournalLineFormSet(request.POST, instance=journal, form_kwargs=line_kwargs)

            if formset.is_valid():
                journal.save()
                formset.save()
                journal.update_totals()
                journal.save()
                return HttpResponse("Journal saved successfully.")
            else:
                return HttpResponse(f"Error in journal lines: {formset.errors}", status=400)
        else:
            return HttpResponse(f"Error in journal header: {form.errors.as_json()}", status=400)

class PostJournalView(View):
    def post(self, request, *args, **kwargs):
        journal = get_object_or_404(Journal, pk=kwargs['journal_id'], organization=request.user.organization)
        if journal.imbalance != Decimal('0.00'):
            return HttpResponse("Cannot post an imbalanced journal.", status=400)
        
        # Add approval logic here
        
        journal.status = 'posted'
        journal.posted_by = request.user
        journal.posted_at = timezone.now()
        journal.is_locked = True
        journal.save()
        
        # Create GL entries
        for line in journal.lines.all():
            GeneralLedger.objects.create(
                organization=journal.organization,
                account=line.account,
                journal=journal,
                journal_line=line,
                period=journal.period,
                transaction_date=journal.journal_date,
                debit_amount=line.debit_amount,
                credit_amount=line.credit_amount,
                # ... and other fields
            )
            
        return HttpResponse("Journal posted successfully.")

class PreviewLedgerImpactView(View):
    def get(self, request, *args, **kwargs):
        journal = get_object_or_404(Journal, pk=kwargs['journal_id'], organization=request.user.organization)
        context = {'journal': journal}
        return HttpResponse(render_to_string('accounting/partials/preview_ledger_impact.html', context))