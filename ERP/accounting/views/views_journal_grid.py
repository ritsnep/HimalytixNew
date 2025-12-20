# accounting/views/views_journal_grid.py
"""
This module contains the views for the journal entry grid.
"""
from decimal import Decimal
from django.shortcuts import render
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.template.loader import render_to_string
from django.db import transaction

from accounting.journal_grid_forms import JournalGridLineForm, JournalGridLineFormSet
from accounting.models import ChartOfAccount
from accounting.forms import JournalForm
from accounting.forms_factory import get_voucher_ui_header
from ..models import JournalLine, Journal

@require_GET
def journal_entry_grid(request):
    header_form = JournalForm(organization=request.organization, ui_schema=get_voucher_ui_header(request.organization))
    line_forms = [JournalGridLineForm(prefix='lines-0', organization=request.organization)]
    context = {
        'header_form': header_form,
        'line_forms': line_forms,
        'next_index': 1,
        'totals': {'debit': '0.00', 'credit': '0.00', 'diff': '0.00'},
    }
    return render(request, 'accounting/journal_entry_grid.html', context)

@require_POST
def journal_entry_grid_add_row(request):
    try:
        next_index = int(request.POST.get('next_index', '0'))
    except ValueError:
        return HttpResponseBadRequest("Invalid index")
    form = JournalGridLineForm(prefix=f'lines-{next_index}', organization=request.organization)
    html = render_to_string('accounting/partials/journal_grid_row.html', {'form': form})
    return HttpResponse(html)

@require_POST
def journal_entry_grid_validate_row(request):
    index = request.POST.get('index')
    if index is None:
        return HttpResponseBadRequest("Index required")
    form = JournalGridLineForm(request.POST, prefix=f'lines-{index}', organization=request.organization)
    if form.is_valid():
        html = render_to_string('accounting/partials/journal_grid_row.html', {'form': form})
        return HttpResponse(html)
    else:
        html = render_to_string('accounting/partials/journal_grid_row.html', {'form': form})
        return HttpResponse(html, status=422)

@require_POST
def journal_entry_grid_paste(request):
    payload = request.POST.get('payload', '')
    start_index = int(request.POST.get('start_index', '0'))
    forms = []
    lines = payload.splitlines()
    for r, line in enumerate(lines):
        cells = [c.strip() for c in line.split('\t')]
        data = {}
        # map cells to fields; adjust order as needed
        keys = ['account', 'description', 'debit_amount', 'credit_amount', 'department', 'project', 'cost_center', 'txn_currency', 'fx_rate', 'memo']
        for i, key in enumerate(keys):
            if i < len(cells):
                data[f'lines-{start_index + r}-{key}'] = cells[i]
        form = JournalGridLineForm(data, prefix=f'lines-{start_index + r}', organization=request.organization)
        forms.append(form)
    html = ''.join(render_to_string('accounting/partials/journal_grid_row.html', {'form': f}) for f in forms)
    return HttpResponse(html)

@require_POST
def journal_entry_grid_save(request):
    header_form = JournalForm(request.POST, organization=request.organization, ui_schema=get_voucher_ui_header(request.organization))
    line_formset = JournalGridLineFormSet(request.POST, prefix='lines', form_kwargs={'organization': request.organization})
    if not header_form.is_valid():
        return HttpResponse("Header invalid", status=422)
    # accumulate totals and objects
    total_debit = 0
    total_credit = 0
    valid_lines = []
    for form in line_formset:
        if not form.is_valid():
            return HttpResponse("Row invalid", status=422)
        cd = form.cleaned_data
        debit = cd.get('debit_amount')
        credit = cd.get('credit_amount')
        account = cd.get('account')
        # ignore blank rows
        if not account and (debit == 0 and credit == 0):
            continue
        total_debit += debit
        total_credit += credit
        valid_lines.append(cd)
    if total_debit == 0 and total_credit == 0:
        return HttpResponse("No lines", status=422)
    if total_debit != total_credit:
        return HttpResponse("Debits and credits must balance", status=422)
    with transaction.atomic():
        journal = header_form.save(commit=False)
        if not journal.pk:
            journal.organization = request.organization
            journal.created_by = request.user
        journal.save()
        for cd in valid_lines:
            JournalLine.objects.create(
                journal=journal,
                account=cd.get('account'),
                description=cd.get('description') or '',
                debit_amount=cd.get('debit_amount') or Decimal('0'),
                credit_amount=cd.get('credit_amount') or Decimal('0'),
                department=cd.get('department'),
                project=cd.get('project'),
                cost_center=cd.get('cost_center'),
                txn_currency=cd.get('txn_currency'),
                fx_rate=cd.get('fx_rate') or Decimal('1'),
                memo=cd.get('memo') or '',
            )
    return HttpResponse("Success")

# Lookup endpoint using existing models; returns account options as HTML
@require_GET
def account_lookup(request):
    q = (request.GET.get('q') or '').strip()
    qs = ChartOfAccount.active_accounts.filter(organization=request.organization)
    if q:
        qs = qs.filter(account_code__icontains=q)[:20]
    # Check if it's an HTMX request
    if request.headers.get('HX-Request'):
        html = render_to_string('accounting/partials/account_select_options.html', {'accounts': qs})
    else:
        html = render_to_string('accounting/partials/account_lookup_options.html', {'accounts': qs})
    return HttpResponse(html)
