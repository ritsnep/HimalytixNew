from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from accounting.forms import JournalForm, JournalLineFormSet
from accounting.models import JournalLine
from accounting.services.journal_entry_service import JournalEntryService
from accounting.validation import JournalValidationService
from utils.htmx import require_htmx

HEADER_EXCLUDE_FIELDS = [
    'journal_date',
    'journal_type',
    'currency_code',
    'exchange_rate',
    'reference',
    'description',
]


@login_required
def journal_entry_new(request):
    organization = request.user.get_active_organization()
    load_partials = True

    if request.method == 'POST':
        load_partials = False
        action = request.POST.get('action') or 'draft'
        form = JournalForm(request.POST, organization=organization)
        formset = JournalLineFormSet(
            request.POST,
            prefix='lines',
            form_kwargs={'organization': organization},
            queryset=JournalLine.objects.none(),
        )

        if form.is_valid() and formset.is_valid():
            service = JournalEntryService(user=request.user, organization=organization)
            journal = service.save_journal(form=form, formset=formset, draft=(action == 'draft'))
            messages.success(request, "Journal saved successfully.")
            if action == 'post':
                return redirect('accounting:voucher_detail', journal.pk)
            return redirect('accounting:journal_entry_edit', journal.pk)

        messages.error(request, "Please correct the errors below.")
    else:
        form = JournalForm(organization=organization)
        formset = JournalLineFormSet(
            prefix='lines',
            form_kwargs={'organization': organization},
            queryset=JournalLine.objects.none(),
        )

    context = {
        'form': form,
        'formset': formset,
        'journal_form': form,
        'line_formset': formset,
        'load_partials_via_htmx': load_partials,
        'header_exclude_fields': HEADER_EXCLUDE_FIELDS,
    }
    return render(request, "accounting/journal_entry.html", context)


@login_required
@require_htmx
def journal_header_partial(request):
    organization = request.user.get_active_organization()
    form = JournalForm(organization=organization)
    return render(
        request,
        "accounting/partials/journal_header_form.html",
        {
            'form': form,
            'journal_form': form,
            'header_exclude_fields': HEADER_EXCLUDE_FIELDS,
        },
    )


@login_required
@require_htmx
def journal_lines_partial(request):
    organization = request.user.get_active_organization()
    formset = JournalLineFormSet(
        prefix='lines',
        form_kwargs={'organization': organization},
        queryset=JournalLine.objects.none(),
    )
    return render(
        request,
        "accounting/partials/journal_lines_table.html",
        {'formset': formset, 'line_formset': formset},
    )


def _render_line_row(form):
    return render_to_string("accounting/partials/journal_line_table_row.html", {'form': form})


@login_required
@require_htmx
@require_POST
def journal_add_line_hx(request):
    organization = request.user.get_active_organization()
    try:
        total_forms = int(request.POST.get('lines-TOTAL_FORMS', 0))
    except (TypeError, ValueError):
        total_forms = 0
    form_kwargs = {'organization': organization}
    form_class = JournalLineFormSet.form
    new_form = form_class(prefix=f'lines-{total_forms}', **form_kwargs)
    row_html = _render_line_row(new_form)
    return HttpResponse(row_html)


@login_required
@require_htmx
@require_POST
def journal_duplicate_line_hx(request):
    try:
        line_index = int(request.POST.get('lineIndex', -1))
    except (TypeError, ValueError):
        line_index = -1
    if line_index < 0:
        return HttpResponse(status=400)

    organization = request.user.get_active_organization()
    try:
        total_forms = int(request.POST.get('lines-TOTAL_FORMS', 0))
    except (TypeError, ValueError):
        total_forms = 0

    line_prefix = f'lines-{line_index}-'
    line_initial = {}
    for key, value in request.POST.items():
        if key.startswith(line_prefix):
            field_name = key.replace(line_prefix, '')
            if field_name in {'id', 'DELETE'}:
                continue
            line_initial[field_name] = value

    form_kwargs = {'organization': organization}
    form_class = JournalLineFormSet.form
    new_form = form_class(
        prefix=f'lines-{total_forms}',
        initial=line_initial,
        **form_kwargs,
    )
    row_html = _render_line_row(new_form)
    return HttpResponse(row_html)


@login_required
@require_htmx
@require_POST
def journal_validate_hx(request):
    organization = request.user.get_active_organization()
    form = JournalForm(request.POST, organization=organization)
    formset = JournalLineFormSet(
        request.POST,
        prefix='lines',
        form_kwargs={'organization': organization},
        queryset=JournalLine.objects.none(),
    )

    header_errors = []
    line_errors = []
    general_errors = []

    if not form.is_valid():
        for field, errors in form.errors.items():
            label = form.fields.get(field).label if field in form.fields else field
            for message in errors:
                header_errors.append({'field': label, 'message': message})

    if not formset.is_valid():
        for idx, line_form in enumerate(formset.forms, start=1):
            if not line_form.errors:
                continue
            for field, errors in line_form.errors.items():
                label = line_form.fields.get(field).label if field in line_form.fields else field
                for message in errors:
                    line_errors.append({'index': idx, 'field': label, 'message': message})

    if form.is_valid() and formset.is_valid():
        validator = JournalValidationService(organization)
        cleaned_lines = [
            line_form.cleaned_data
            for line_form in formset.forms
            if line_form.cleaned_data and not line_form.cleaned_data.get('DELETE')
        ]
        validation_result = validator.validate_journal_entry(form.cleaned_data, cleaned_lines)
        for field, message in validation_result.get('header', {}).items():
            header_errors.append({'field': field, 'message': message})
        for entry in validation_result.get('lines', []):
            idx = entry.get('index', 0) + 1
            for field, message in entry.get('errors', {}).items():
                if isinstance(message, (list, tuple)):
                    for detail in message:
                        line_errors.append({'index': idx, 'field': field, 'message': detail})
                else:
                    line_errors.append({'index': idx, 'field': field, 'message': message})
        general_errors.extend(validation_result.get('general', []))

    context = {
        'header_errors': header_errors,
        'line_errors': line_errors,
        'general_errors': general_errors,
        'has_errors': bool(header_errors or line_errors or general_errors),
    }
    return render(request, "accounting/partials/journal_validation_summary.html", context)
