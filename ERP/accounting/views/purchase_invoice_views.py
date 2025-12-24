from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from django.forms import formset_factory
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from accounting.forms_factory import VoucherFormFactory
from accounting.forms import (
    PurchaseInvoiceForm,
    PurchaseInvoiceLineForm,
    PurchaseInvoiceLineFormSet,
    PurchasePaymentForm,
)
from accounting.models import VoucherModeConfig, PurchaseInvoice, PurchaseInvoiceLine, APPayment, ChartOfAccount, Vendor
from accounting.services.agent_service import AgentService
from accounting.services.purchase_calculator import PurchaseCalculator


def _get_cash_bank_choices(organization):
    from django.db.models import Q

    cash_bank_accounts = ChartOfAccount.objects.filter(
        Q(organization=organization),
        Q(account_type__name__in=['Cash', 'Bank']) | Q(is_bank_account=True),
        is_active=True,
    ).distinct()
    account_choices = [('', 'Select account')]
    account_choices.extend([(str(acct.pk), f"{acct.code} - {acct.name}") for acct in cash_bank_accounts])
    return account_choices, cash_bank_accounts


def _parse_invoice_date(data):
    raw = data.get('invoice_date')
    if not raw:
        return None
    date_field = forms.DateField(required=False)
    try:
        return date_field.clean(raw)
    except ValidationError:
        return None


def _sum_payment_amounts(payment_formset):
    total = Decimal('0')
    for form in payment_formset:
        data = getattr(form, 'cleaned_data', None)
        if not data or data.get('DELETE'):
            continue
        amount = data.get('amount')
        if amount:
            total += Decimal(str(amount))
    return total


@login_required
@require_http_methods(["GET", "POST"])
@csrf_protect
def purchase_invoice_new_enhanced(request):
    """Enhanced purchase invoice form with HTMX integration"""
    organization = request.user.get_active_organization()

    def _build_payment_formset(data=None, invoice_date=None):
        account_choices, cash_bank_accounts = _get_cash_bank_choices(organization)
        PaymentFormSet = formset_factory(PurchasePaymentForm, extra=0, can_delete=True)
        form_kwargs = {
            'invoice_date': invoice_date,
            'cash_bank_choices': account_choices,
        }
        if data is None:
            return PaymentFormSet(prefix='payments', form_kwargs=form_kwargs), cash_bank_accounts, account_choices
        return PaymentFormSet(data, prefix='payments', form_kwargs=form_kwargs), cash_bank_accounts, account_choices

    if request.method == 'GET':
        form = PurchaseInvoiceForm(organization=organization)
        # Get empty queryset for display (HTMX will handle adding items)
        line_items = PurchaseInvoiceLine.objects.none()

        # Prepare empty inline formset for items so management form fields exist
        # Use unbound formset (no instance) to avoid BaseFormSet __init__ errors
        line_formset = PurchaseInvoiceLineFormSet(prefix='items', form_kwargs={'organization': organization})

        # Prepare payments formset (simple formset) for management form
        invoice_date = timezone.now().date()
        payments_formset, cash_bank_accounts, _ = _build_payment_formset(invoice_date=invoice_date)

        context = {
            'form': form,
            'line_items': line_items,
            'line_formset': line_formset,
            'payments_formset': payments_formset,
            'cash_bank_accounts': cash_bank_accounts,
            'agents': AgentService.get_agents_for_dropdown(organization),
            'areas': AgentService.get_areas_for_dropdown(organization),
        }
        return render(request, 'accounting/purchase/new_enhanced.html', context)
    
    elif request.method == 'POST':
        form = PurchaseInvoiceForm(request.POST, organization=organization)

        invoice_date_value = _parse_invoice_date(request.POST)
        payments_formset, cash_bank_accounts, _ = _build_payment_formset(request.POST, invoice_date=invoice_date_value)

        invoice_stub = PurchaseInvoice(organization=organization)
        line_formset = PurchaseInvoiceLineFormSet(
            request.POST,
            prefix='items',
            instance=invoice_stub,
            form_kwargs={'organization': organization},
        )

        form_valid = form.is_valid()
        lines_valid = line_formset.is_valid()
        payments_valid = payments_formset.is_valid()

        if form_valid and lines_valid and payments_valid:
            valid_lines = [
                f for f in line_formset.forms
                if f.cleaned_data and not f.cleaned_data.get('DELETE') and f.has_changed()
            ]
            if not valid_lines:
                form.add_error(None, "At least one line item is required.")
                form_valid = False

        if form_valid and lines_valid and payments_valid:
            from accounting.services.validation_service import ValidationService

            header_discount_value = form.cleaned_data.get('discount_value') or 0
            header_discount_type = form.cleaned_data.get('discount_type') or 'amount'
            bill_rounding = form.cleaned_data.get('bill_rounding') or 0
            calc_lines = []
            validation_lines = []
            for line_form in line_formset.forms:
                if not line_form.cleaned_data or line_form.cleaned_data.get('DELETE'):
                    continue
                qty = line_form.cleaned_data.get('quantity') or 0
                rate = line_form.cleaned_data.get('unit_cost') or 0
                vat_rate = line_form.cleaned_data.get('vat_rate') or 0
                calc_lines.append({
                    'qty': qty,
                    'rate': rate,
                    'vat_applicable': Decimal(str(vat_rate)) > 0,
                    'row_discount_value': line_form.cleaned_data.get('discount_amount') or 0,
                    'row_discount_type': 'amount',
                })
                product = line_form.cleaned_data.get('product')
                warehouse = line_form.cleaned_data.get('warehouse')
                validation_line = {
                    'quantity': qty,
                    'rate': rate,
                }
                if product:
                    validation_line['product_id'] = product.pk
                if warehouse:
                    validation_line['warehouse_id'] = warehouse.pk
                validation_lines.append(validation_line)

            calc = PurchaseCalculator(
                lines=calc_lines,
                header_discount_value=header_discount_value,
                header_discount_type=header_discount_type,
                bill_rounding=bill_rounding,
            )
            totals = calc.compute()
            total_amount = totals.get('totals', {}).get('grand_total') or Decimal('0')

            payment_sum = _sum_payment_amounts(payments_formset)
            if payment_sum > total_amount:
                form.add_error(None, 'Payment total exceeds invoice total.')
                form_valid = False

            if form_valid:
                validation_errors = ValidationService.validate_purchase_invoice_data(
                    organization,
                    {
                        'vendor_id': form.cleaned_data['vendor'].pk if form.cleaned_data.get('vendor') else None,
                        'line_items': validation_lines,
                        'total_amount': total_amount,
                        'calculated_total': total_amount,
                        'expected_total': total_amount,
                        'grand_total': total_amount,
                        'payments_total': payment_sum,
                    },
                )
                if validation_errors:
                    for key, err in validation_errors.items():
                        form.add_error(None, f"{key}: {err}")
                    form_valid = False

        if form_valid and lines_valid and payments_valid:
            try:
                with transaction.atomic():
                    invoice = form.save(commit=False)
                    invoice.organization = organization
                    invoice.created_by = request.user
                    agent_area_id = request.POST.get('agent_area_id')
                    if agent_area_id:
                        from accounting.models import Area
                        area = Area.objects.filter(organization=organization, area_id=agent_area_id).first()
                        invoice.agent_area = area.name if area else str(agent_area_id)
                    invoice.save()

                    # Re-bind line formset with actual invoice for saving
                    line_formset = PurchaseInvoiceLineFormSet(
                        request.POST,
                        prefix='items',
                        instance=invoice,
                        form_kwargs={'organization': organization},
                    )
                    if line_formset.is_valid():
                        # Save lines
                        line_objects = line_formset.save(commit=False)
                        for obj in line_objects:
                            obj.invoice = invoice
                            obj.save()
                        # Handle deletions
                        for obj in line_formset.deleted_objects:
                            obj.delete()
                    else:
                        raise ValueError(f"Line items invalid: {line_formset.errors}")

                    # Process payments
                    if payments_formset.is_valid():
                        from accounting.models import APPayment, APPaymentLine, Currency
                        saved_payments = []
                        for idx, pform in enumerate(payments_formset.cleaned_data):
                            if not pform or pform.get('DELETE'):
                                continue
                            amount = pform.get('amount') or 0
                            if float(amount) <= 0:
                                continue
                            payment_method = pform.get('payment_method') or 'bank'
                            bank_id = pform.get('cash_bank_id')
                            bank_account = None
                            if bank_id:
                                try:
                                    bank_account = ChartOfAccount.objects.get(pk=int(bank_id), organization=organization)
                                except Exception:
                                    bank_account = None

                            payment_number = f"PY-{invoice.pk}-{len(saved_payments)+1}"
                            ap = APPayment.objects.create(
                                organization=organization,
                                vendor=invoice.vendor,
                                payment_number=payment_number,
                                payment_date=pform.get('due_date') or invoice.invoice_date,
                                payment_method=payment_method,
                                bank_account=bank_account or ChartOfAccount.objects.filter(organization=organization, is_bank_account=True).first(),
                                currency=invoice.currency or Currency.objects.filter(is_active=True).first(),
                                exchange_rate=invoice.exchange_rate or 1,
                                amount=amount,
                                discount_taken=0,
                                status='draft',
                                created_by=request.user,
                            )
                            # Link payment line to invoice
                            APPaymentLine.objects.create(
                                payment=ap,
                                invoice=invoice,
                                applied_amount=amount,
                                discount_taken=0,
                            )
                            saved_payments.append(ap)

                    agent_id = request.POST.get('agent_id')
                    if agent_id:
                        invoice.metadata = dict(invoice.metadata or {})
                        invoice.metadata['agent_id'] = agent_id
                        invoice.save(update_fields=['metadata'])

                    # Success
                    context = {
                        'form': form,
                        'line_items': PurchaseInvoiceLine.objects.none(),
                        'line_formset': line_formset,
                        'payments_formset': payments_formset,
                        'cash_bank_accounts': cash_bank_accounts,
                        'agents': AgentService.get_agents_for_dropdown(organization),
                        'areas': AgentService.get_areas_for_dropdown(organization),
                        'alert_message': 'Purchase Invoice created successfully.',
                        'alert_level': 'success',
                    }
                    response = render(request, 'accounting/purchase/new_enhanced.html', context)
                    response['HX-Trigger'] = 'purchaseInvoiceSaved'
                    return response
            except Exception as e:
                form.add_error(None, f"Error saving invoice: {str(e)}")

        # Re-display form with errors
        line_items = PurchaseInvoiceLine.objects.none()
        context = {
            'form': form,
            'line_items': line_items,
            'line_formset': line_formset,
            'payments_formset': payments_formset,
            'cash_bank_accounts': cash_bank_accounts,
            'agents': AgentService.get_agents_for_dropdown(organization),
            'areas': AgentService.get_areas_for_dropdown(organization),
        }
        status = 422 if _is_htmx(request) else 200
        return render(request, 'accounting/purchase/new_enhanced.html', context, status=status)


@require_http_methods(["GET", "POST"])
def purchase_add_line_hx(request):
    """Return a rendered blank purchase line row for HTMX add-line actions."""
    organization = request.user.get_active_organization()
    form_count = request.GET.get('form_count') or request.POST.get('form_count') or '0'
    try:
        form_index = int(form_count)
    except Exception:
        form_index = 0

    prefix_val = request.GET.get('prefix') or request.POST.get('prefix') or 'lines'
    variant = request.GET.get('variant') or request.POST.get('variant') or 'default'
    # Create a PurchaseInvoice product line form (not a generic journal line)
    from accounting.forms import PurchaseInvoiceLineForm
    form_prefix = f"{prefix_val}-{form_index}"
    blank_line = PurchaseInvoiceLineForm(prefix=form_prefix, organization=organization)

    context = {
        'form': blank_line,
        'form_index': form_index,
    }
    template_name = 'accounting/partials/_purchase_line_row.html'
    if variant == 'enhanced':
        template_name = 'accounting/purchase/_line_row_new.html'
    return render(request, template_name, context)


@require_http_methods(["POST"])
def purchase_remove_line_hx(request):
    """Handle line removal and re-render the lines table partial.

    Expects the full formset data to be posted (so DELETE marker can be applied server-side),
    then returns the updated lines table HTML for replacement.
    """
    organization = request.user.get_active_organization()
    # Bind the posted purchase header and line formset so management form indexes are correct
    from accounting.forms import PurchaseInvoiceForm, PurchaseInvoiceLineForm
    prefix_val = request.POST.get('prefix') or request.GET.get('prefix') or 'items'
    header_form = PurchaseInvoiceForm(data=request.POST, organization=organization)
    PurchaseInvoiceLineFormSet_local = forms.formset_factory(PurchaseInvoiceLineForm, can_delete=True)
    line_formset = PurchaseInvoiceLineFormSet_local(data=request.POST, prefix=prefix_val)

    # We don't require the forms to be valid to re-render; just show updated rows
    context = {'line_formset': line_formset}
    return render(request, 'accounting/partials/_purchase_lines_table.html', context)


@require_http_methods(["POST"])
def purchase_recalc_hx(request):
    """Recalculate per-row and totals using posted header + lines; return combined partial.

    Returns the combined HTML fragment for replacement of the recalc region.
    """
    organization = request.user.get_active_organization()
    from accounting.forms import PurchaseInvoiceForm, PurchaseInvoiceLineForm
    prefix_val = request.POST.get('prefix') or request.GET.get('prefix') or 'items'
    header_form = PurchaseInvoiceForm(data=request.POST, organization=organization)
    PurchaseInvoiceLineFormSet_local = forms.formset_factory(PurchaseInvoiceLineForm, can_delete=True)
    line_formset = PurchaseInvoiceLineFormSet_local(data=request.POST, prefix=prefix_val)

    # Extract data for calculator
    header_data = header_form.cleaned_data if header_form.is_valid() else {}
    lines = []
    for form in line_formset.forms:
        if not getattr(form, 'cleaned_data', None):
            # if not bound/valid, try initial data
            data = form.initial or {}
        else:
            data = form.cleaned_data
        if data.get('DELETE'):
            continue
        vat_rate = data.get('vat_rate')
        vat_applicable = (
            data.get('vat') in (True, 'Yes', 'yes', 'Y', 'y')
            or data.get('vat_applicable') in (True, 'Yes')
            or (vat_rate is not None and float(vat_rate) > 0)
        )
        # normalize expected keys
        lines.append({
            'qty': data.get('qty') or data.get('quantity') or 0,
            'rate': data.get('rate') or data.get('unit_cost') or data.get('unit_price') or 0,
            'vat_applicable': vat_applicable,
            'row_discount_value': data.get('discount') or data.get('discount_amount') or 0,
            'row_discount_type': data.get('discount_type') or 'amount',
        })

    # Header discount and rounding
    header_discount_value = (
        header_data.get('header_discount_value')
        or header_data.get('discount_value')
        or header_data.get('discount')
        or 0
    )
    header_discount_type = (
        header_data.get('header_discount_type')
        or header_data.get('discount_type')
        or 'amount'
    )
    bill_rounding = header_data.get('bill_rounding') or header_data.get('rounding') or 0

    calc = PurchaseCalculator(
        lines=lines,
        header_discount_value=header_discount_value,
        header_discount_type=header_discount_type,
        bill_rounding=bill_rounding
    )
    result = calc.compute()

    context = {
        'line_formset': line_formset,
        'calc_rows': result['rows'],
        'totals': result['totals'],
    }

    return render(request, 'accounting/partials/_purchase_recalc_region.html', context)


@require_http_methods(["GET"])
def purchase_add_payment_hx(request):
    """Return a rendered blank payment row for HTMX add-payment actions."""
    organization = request.user.get_active_organization()
    form_count = request.GET.get('form_count') or request.POST.get('form_count') or '0'
    try:
        form_index = int(form_count)
    except Exception:
        form_index = 0

    variant = request.GET.get('variant') or request.POST.get('variant') or 'default'
    # Simple payment form rendering uses existing widgets; prefix 'payments'

    template_name = 'accounting/partials/_purchase_payment_row.html'
    if variant == 'enhanced':
        invoice_date = timezone.now().date()
        cash_bank_choices, _ = _get_cash_bank_choices(organization)
        PaymentForm = PurchasePaymentForm(
            prefix=f'payments-{form_index}',
            invoice_date=invoice_date,
            cash_bank_choices=cash_bank_choices,
        )
        template_name = 'accounting/purchase/_payment_row_new.html'
    else:
        class _PaymentForm(forms.Form):
            payment_ledger = forms.CharField(required=False)
            amount = forms.DecimalField(required=False, max_digits=19, decimal_places=4)
            note = forms.CharField(required=False)
            DELETE = forms.BooleanField(required=False)

        PaymentForm = _PaymentForm(prefix=f'payments-{form_index}')

    context = {
        'form': PaymentForm,
        'form_index': form_index,
    }
    return render(request, template_name, context)


@require_http_methods(["POST"])
def purchase_apply_order_hx(request):
    """Import lines from an order reference and return appended rows + trigger recalc."""
    organization = request.user.get_active_organization()
    order_ref = (
        request.POST.get('order_reference') or
        request.POST.get('order_ref') or
        request.POST.get('purchase_order') or
        request.GET.get('order_reference') or
        request.GET.get('purchase_order')
    )
    form_count = request.POST.get('form_count') or request.GET.get('form_count') or '0'
    try:
        start_index = int(form_count)
    except Exception:
        start_index = 0

    imported = []
    if order_ref:
        from accounting.services.order_import_service import import_purchase_order_lines
        imported = import_purchase_order_lines(organization, order_ref)

    forms = []
    for idx, item in enumerate(imported):
        fi = start_index + idx
        form = VoucherFormFactory.create_blank_line_form(organization=organization, form_index=fi)
        # Populate initial values expected by line form
        form.initial.update({
            'quantity': item.get('quantity', 0),
            'rate': item.get('unit_cost', 0),
            'unit': item.get('unit'),
            'godown': item.get('godown'),
            'po_reference': item.get('po_line_id') or item.get('po_reference'),
        })
        forms.append({'form': form, 'form_index': fi})

    context = {'import_forms': forms}
    # Return partial with rows and an auto-triggered recalc loader
    return render(request, 'accounting/partials/_purchase_import_rows_and_recalc.html', context)


@require_http_methods(["POST"])
def purchase_remove_payment_hx(request):
    """Handle payment removal and re-render the payments table partial."""
    # Bind posted payment formset and re-render
    from django import forms
    variant = request.POST.get('variant') or request.GET.get('variant') or 'default'

    if variant == 'enhanced' or any(key.endswith('-payment_method') for key in request.POST.keys()):
        class PaymentForm(forms.Form):
            payment_method = forms.CharField(required=False)
            cash_bank_id = forms.CharField(required=False)
            due_date = forms.DateField(required=False)
            amount = forms.DecimalField(required=False, max_digits=19, decimal_places=4)
            remarks = forms.CharField(required=False)
            DELETE = forms.BooleanField(required=False)
        template_name = 'accounting/purchase/_payments_table_new.html'
    else:
        class PaymentForm(forms.Form):
            payment_ledger = forms.CharField(required=False)
            amount = forms.DecimalField(required=False, max_digits=19, decimal_places=4)
            note = forms.CharField(required=False)
            DELETE = forms.BooleanField(required=False)
        template_name = 'accounting/partials/_purchase_payments_table.html'

    PaymentFormSet = forms.formset_factory(PaymentForm, can_delete=True)
    payment_formset = PaymentFormSet(data=request.POST, prefix='payments')

    context = {'payment_formset': payment_formset}
    return render(request, template_name, context)


@require_http_methods(["POST"])
def purchase_payment_recalc_hx(request):
    """Recalculate remaining balance given header+lines+payments; return payments + remaining partials."""
    organization = request.user.get_active_organization()
    from django import forms
    from decimal import Decimal

    # Re-use existing line calculator to obtain grand total
    header_form = VoucherFormFactory.get_journal_form(organization=organization, data=request.POST)
    line_formset = VoucherFormFactory.get_journal_line_formset(organization=organization, data=request.POST)

    # Build lines for calculator (same logic as purchase_recalc_hx)
    lines = []
    for form in line_formset.forms:
        data = form.cleaned_data if getattr(form, 'cleaned_data', None) else form.initial or {}
        if data.get('DELETE'):
            continue
        lines.append({
            'qty': data.get('qty') or data.get('quantity') or 0,
            'rate': data.get('rate') or 0,
            'vat_applicable': data.get('vat') in (True, 'Yes', 'yes', 'Y', 'y') or data.get('vat_applicable') in (True, 'Yes'),
            'row_discount_value': data.get('discount') or 0,
            'row_discount_type': data.get('discount_type') or 'amount',
        })

    header_data = header_form.cleaned_data if header_form.is_valid() else {}
    header_discount_value = (
        header_data.get('header_discount_value')
        or header_data.get('discount_value')
        or header_data.get('discount')
        or 0
    )
    header_discount_type = (
        header_data.get('header_discount_type')
        or header_data.get('discount_type')
        or 'amount'
    )
    bill_rounding = header_data.get('bill_rounding') or 0

    calc = PurchaseCalculator(
        lines=lines,
        header_discount_value=header_discount_value,
        header_discount_type=header_discount_type,
        bill_rounding=bill_rounding,
    )
    result = calc.compute()
    grand_total = result['totals'].get('grand_total') or Decimal('0')

    # Bind payments
    if any(key.endswith('-payment_method') for key in request.POST.keys()):
        class PaymentForm(forms.Form):
            payment_method = forms.CharField(required=False)
            cash_bank_id = forms.CharField(required=False)
            due_date = forms.DateField(required=False)
            amount = forms.DecimalField(required=False, max_digits=19, decimal_places=4)
            remarks = forms.CharField(required=False)
            DELETE = forms.BooleanField(required=False)
    else:
        class PaymentForm(forms.Form):
            payment_ledger = forms.CharField(required=False)
            amount = forms.DecimalField(required=False, max_digits=19, decimal_places=4)
            note = forms.CharField(required=False)
            DELETE = forms.BooleanField(required=False)

    PaymentFormSet = forms.formset_factory(PaymentForm, can_delete=True)
    payment_formset = PaymentFormSet(data=request.POST, prefix='payments')

    payment_sum = Decimal('0')
    if payment_formset.is_valid():
        for f in payment_formset.forms:
            if f.cleaned_data.get('DELETE'):
                continue
            amt = f.cleaned_data.get('amount') or 0
            payment_sum += Decimal(str(amt))
    else:
        # Fallback: try to read raw POST values
        idx = 0
        while True:
            key = f'payments-{idx}-amount'
            if key not in request.POST:
                break
            raw = request.POST.get(key) or '0'
            try:
                payment_sum += Decimal(raw)
            except Exception:
                pass
            idx += 1

    remaining = grand_total - payment_sum

    context = {
        'payment_formset': payment_formset,
        'remaining': remaining,
        'totals': result['totals'],
    }
    # Return combined payments table and remaining balance partials (wrapper partial)
    return render(request, 'accounting/partials/_purchase_payments_region.html', context)


@require_http_methods(["GET"])
def purchase_supplier_summary_hx(request):
    """Return supplier summary panel when supplier changes. Respects organization scope."""
    organization = request.user.get_active_organization()
    vendor_id = request.GET.get('vendor') or request.GET.get('supplier')
    vendor = None
    if vendor_id:
        try:
            vendor = Vendor.objects.get(pk=vendor_id, organization=organization)
        except Vendor.DoesNotExist:
            vendor = None

    # Use aging service to compute outstanding if vendor present
    balance = None
    outstanding = None
    last_invoice = None
    credit_limit = None
    if vendor:
        from accounting.services.ap_aging_service import APAgingService
        aging = APAgingService(organization)
        rows = aging.build()
        # find row for vendor
        vendor_row = next((r for r in rows if r.vendor_id == vendor.vendor_id), None)
        outstanding = vendor_row.total if vendor_row else 0
        # current balance: positive outstanding means vendor is owed (Dr)
        balance = outstanding
        last_invoice = (
            PurchaseInvoice.objects.filter(organization=organization, vendor=vendor).order_by('-invoice_date').first()
        )
        credit_limit = vendor.credit_limit

    context = {
        'vendor': vendor,
        'balance': balance,
        'outstanding': outstanding,
        'last_invoice': last_invoice,
        'credit_limit': credit_limit,
    }
    return render(request, 'accounting/partials/_supplier_summary_panel.html', context)
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View

from accounting.forms import PurchaseInvoiceForm, PurchaseInvoiceLineForm
from accounting.models import Vendor
from accounting.services.purchase_invoice_service import PurchaseInvoiceService
from accounting.views.views_mixins import AccountsPayablePermissionMixin

VendorBillLineFormSet = forms.formset_factory(
    PurchaseInvoiceLineForm,
    extra=1,
    can_delete=True,
)

def _is_htmx(request) -> bool:
    return request.headers.get("HX-Request") == "true" or getattr(request, "htmx", False)


class VendorBillCreateView(AccountsPayablePermissionMixin, View):
    template_name = "accounting/vendor_bill_form.html"
    permission_tuple = ("accounting", "purchaseinvoice", "add")

    def get(self, request):
        organization = self.get_organization()
        context = self._build_context(
            organization,
            PurchaseInvoiceForm(organization=organization, initial={'organization': organization}),
            self._build_line_formset(organization),
        )
        return render(request, self.template_name, context)

    def post(self, request):
        organization = self.get_organization()
        form = PurchaseInvoiceForm(data=request.POST, organization=organization)
        line_formset = self._build_line_formset(organization, data=request.POST)
        context = self._build_context(organization, form, line_formset)
        if not (form.is_valid() and line_formset.is_valid()):
            if _is_htmx(request):
                return render(request, self.template_name, context, status=422)
            return render(request, self.template_name, context)

        lines = []
        for line_form in line_formset:
            if not line_form.has_changed() or line_form.cleaned_data.get("DELETE"):
                continue
            data = line_form.cleaned_data
            lines.append(
                {
                    "description": data.get("description"),
                    "product_code": data.get("product_code"),
                    "quantity": data.get("quantity"),
                    "unit_cost": data.get("unit_cost"),
                    "discount_amount": data.get("discount_amount"),
                    "account": data.get("account"),
                    "tax_code": data.get("tax_code"),
                    "tax_amount": data.get("tax_amount"),
                    "cost_center": data.get("cost_center"),
                    "department": data.get("department"),
                    "project": data.get("project"),
                    "dimension_value": data.get("dimension_value"),
                    "po_reference": data.get("po_reference"),
                    "receipt_reference": data.get("receipt_reference"),
                }
            )

        if not lines:
            form.add_error(None, "At least one line item is required.")
            if _is_htmx(request):
                return render(request, self.template_name, context, status=422)
            return render(request, self.template_name, context)

        try:
            service = PurchaseInvoiceService(request.user)
            invoice = service.create_invoice(
                organization=organization,
                vendor=form.cleaned_data["vendor"],
                invoice_number=form.cleaned_data["invoice_number"],
                invoice_date=form.cleaned_data["invoice_date"],
                currency=form.cleaned_data["currency"],
                exchange_rate=form.cleaned_data.get("exchange_rate") or Decimal("1"),
                lines=lines,
                payment_term=form.cleaned_data.get("payment_term"),
                due_date=form.cleaned_data.get("due_date"),
                metadata={},
            )
            invoice.external_reference = form.cleaned_data.get("external_reference") or ""
            invoice.po_number = form.cleaned_data.get("po_number") or ""
            invoice.receipt_reference = form.cleaned_data.get("receipt_reference") or ""
            invoice.notes = form.cleaned_data.get("notes") or ""
            invoice.save(
                update_fields=["external_reference", "po_number", "receipt_reference", "notes"]
            )
        except ValidationError as exc:
            form.add_error(None, exc)
            if _is_htmx(request):
                return render(request, self.template_name, context, status=422)
            return render(request, self.template_name, context)

        context["alert_message"] = "Vendor bill saved as draft."
        context["alert_level"] = "success"
        if _is_htmx(request):
            return render(request, self.template_name, context)
        messages.success(request, context["alert_message"])
        return redirect(reverse("accounting:vendor_bill_create"))

    def _build_line_formset(self, organization, data=None):
        kwargs = {"prefix": "lines", "form_kwargs": {"organization": organization}}
        if data is not None:
            kwargs["data"] = data
        return VendorBillLineFormSet(**kwargs)

    def _build_context(self, organization, form, line_formset):
        return {
            "form": form,
            "line_formset": line_formset,
            "line_row_url": reverse("accounting:vendor_bill_line_row"),
            "vendor_summary_url": reverse("accounting:vendor_summary_hx"),
            "organization": organization,
        }


class VendorBillLineRowView(AccountsPayablePermissionMixin, View):
    template_name = "accounting/partials/purchase_invoice_line_row.html"
    permission_tuple = ("accounting", "purchaseinvoice", "add")

    def get(self, request):
        organization = self.get_organization()
        index = request.GET.get("index", "0")
        try:
            int_index = int(index)
        except ValueError:
            int_index = 0
        prefix = f"lines-{int_index}"
        form = PurchaseInvoiceLineForm(prefix=prefix, organization=organization)
        return render(request, self.template_name, {"form": form})


class VendorSummaryHXView(AccountsPayablePermissionMixin, View):
    template_name = "accounting/partials/vendor_summary.html"
    permission_tuple = ("accounting", "purchaseinvoice", "add")

    def get(self, request):
        organization = self.get_organization()
        vendor_id = request.GET.get("vendor")
        vendor = None
        if vendor_id:
            try:
                vendor = Vendor.objects.get(pk=vendor_id, organization=organization)
            except Vendor.DoesNotExist:
                vendor = None
        return render(request, self.template_name, {"vendor": vendor})


# ===== DEPRECATION NOTICE =====
# The VendorBillCreateView below is deprecated.
# Use purchasing:invoice-create instead for the unified purchasing workflow.

def vendor_bill_create_deprecated(request):
    """
    Deprecated: This endpoint is no longer maintained.
    Redirect users to the new unified purchasing flow in purchasing module.
    
    The unified flow at purchasing:invoice-create provides:
    - Better integration with POs and GRs
    - Real-time calculations
    - GL integration
    - Landed cost allocation
    """
    from django.contrib import messages
    from django.shortcuts import redirect
    from django.urls import reverse

    messages.info(
        request,
        "Vendor Bill Entry has been moved to the Purchasing module for better workflow integration. "
        "Redirecting to Purchase Invoice form..."
    )
    return redirect(reverse("purchasing:invoice-create"))


# New HTMX endpoints that call the implemented services
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from accounting.services.vendor_service import VendorService
from inventory.services import ProductService
from accounting.services.pricing_service import PricingService
from accounting.services.agent_service import AgentService
from accounting.services.validation_service import ValidationService
from accounting.services.notification_service import NotificationService
from accounting.services.document_sequence_service import DocumentSequenceService
from accounting.services.chart_of_account_service import ChartOfAccountService
from purchasing.services.purchase_order_service import PurchaseOrderQueryService
from accounting.services.payment_term_service import PaymentTermService
from inventory.services.inventory_service import WarehouseService
from inventory.models import Unit
import json


@require_http_methods(["GET"])
def search_products_hx(request):
    """HTMX endpoint for product search with autocomplete."""
    organization = request.user.get_active_organization()
    query = request.GET.get('q', '').strip()
    form_index = request.GET.get('form_index', '0')

    if len(query) < 2:
        return render(request, 'accounting/partials/_product_search_results.html', {'results': []})

    try:
        from inventory.models import Product
        products = Product.objects.filter(organization=organization)

        # Don't filter by is_active since Product model doesn't have this field
        # if hasattr(Product, 'is_active'):
        #     products = products.filter(is_active=True)

        if query:
            products = (
                products.filter(code__icontains=query)
                | products.filter(name__icontains=query)
                | products.filter(barcode__icontains=query)
            )

        products = products.order_by('code')[:10]

        results = []
        for product in products:
            unit_name = product.base_unit.name if product.base_unit else 'Nos'
            results.append({
                'id': product.id,
                'text': f"{product.code} - {product.name}",
                'code': product.code or '',
                'name': product.name,
                'unit': unit_name,
                'hs_code': product.hs_code or '',
            })

        return render(request, 'accounting/partials/_product_search_results.html', {
            'results': results,
            'form_index': form_index
        })

    except Exception as e:
        return render(request, 'accounting/partials/_product_search_results.html', {'results': []})


@require_http_methods(["GET"])
def get_fiscal_year_hx(request):
    """Get current fiscal year for the organization."""
    organization = request.user.get_active_organization()
    # TODO: Implement proper fiscal year service
    return JsonResponse({'fiscal_year': '82/83'})


def purchase_invoice_form(request):
    """Render the main purchase invoice form"""
    organization = request.user.get_active_organization()
    context = {
        'voucher_prefix': 'PB',
        'fiscal_year': '82/83',  # Get from FiscalYearService
        'suppliers': VendorService.get_vendors_for_dropdown(organization),
        'purchase_accounts': ChartOfAccountService.get_purchase_accounts_for_dropdown(organization),
        'agents': AgentService.get_agents_for_dropdown(organization),
        'areas': AgentService.get_areas_for_dropdown(organization),
        'orders': PurchaseOrderQueryService.get_pending_orders_for_dropdown(organization),
        'terms': PaymentTermService.get_payment_terms_for_dropdown(organization),
        'godowns': WarehouseService.get_warehouses_for_dropdown(organization),
        'payment_ledgers': ChartOfAccountService.get_payment_ledgers_for_dropdown(organization),
        'items': ProductService.get_products_for_dropdown(organization),
        'units': [{'code': u.code, 'name': u.name} for u in Unit.objects.filter(organization=organization, is_active=True)],
    }
    return render(request, 'accounting/purchaseinvoice_mockup.html', context)


def load_vendor_details(request, vendor_id):
    """Load vendor details via HTMX"""
    if request.method == 'POST':
        vendor_id = request.POST.get('party_ledger_id')
    
    try:
        organization = request.user.get_active_organization()
        details = VendorService.get_vendor_details(organization, vendor_id)
        agent_info = AgentService.auto_select_agent_for_vendor(organization, vendor_id)

        return JsonResponse({
            'success': True,
            'supplier_info': f"Balance: NPR {details['balance']:.2f} | PAN: {details['pan']} | Credit Limit: NPR {details['credit_limit']:.2f}",
            'agent_id': agent_info['agent_id'],
            'area_id': agent_info['area_id'],
            'due_days': 30,  # From vendor payment terms
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def load_product_details(request, product_id):
    """Load product details for line item"""
    if request.method == 'POST':
        product_id = request.POST.get('item_id')
    
    try:
        organization = request.user.get_active_organization()
        product = ProductService.get_product_details(organization, product_id)
        vendor_id = request.POST.get('party_ledger_id') or request.GET.get('vendor_id')

        pricing = {'standard_price': product.get('standard_price', 0)}
        if vendor_id:
            pricing = PricingService.get_pricing_for_party(organization, product_id, int(vendor_id))

        rate = pricing.get('party_price', pricing.get('standard_price', 0))

        return JsonResponse({
            'success': True,
            'code': product.get('code') or '',
            'hs_code': product['hs_code'],
            'description': product['description'],
            'unit': product['unit'],
            'vat_applicable': product['vat_applicable'],
            'vat_rate': product.get('vat_rate', 0),
            'rate': rate,
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_POST
def calculate_invoice_totals(request):
    """Calculate and return invoice totals"""
    try:
        organization = request.user.get_active_organization()
        
        # Parse line items from form data
        line_items = []
        item_count = 0
        
        # Parse form data to extract line items
        for key, value in request.POST.items():
            if key.startswith('lines-') and key.endswith('-item_id'):
                # This is a line item
                index = key.split('-')[1]
                line_item = {
                    'item_id': request.POST.get(f'lines-{index}-item_id'),
                    'quantity': request.POST.get(f'lines-{index}-qty', 0),
                    'rate': request.POST.get(f'lines-{index}-rate', 0),
                    'discount': request.POST.get(f'lines-{index}-discount_value', 0),
                    'vat_rate': 13.0 if request.POST.get(f'lines-{index}-vat_applicable') == 'yes' else 0.0,
                }
                line_items.append(line_item)

        header_discount = {
            'value': request.POST.get('hdr_discount_value', 0),
            'type': request.POST.get('hdr_discount_type', 'amount')
        }

        # Import the purchase invoice service
        from accounting.services.purchase_invoice_service import PurchaseInvoiceService

        totals = PurchaseInvoiceService.calculate_totals(organization, line_items, header_discount)

        return JsonResponse({
            'success': True,
            'totals': totals,
            'in_words': PurchaseInvoiceService.amount_to_words(totals['grand_total']),
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_POST
def save_purchase_invoice(request):
    """Save the purchase invoice"""
    try:
        organization = request.user.get_active_organization()
        
        # Parse form data into invoice structure
        data = {
            'voucher_prefix': request.POST.get('voucher_prefix'),
            'voucher_no': request.POST.get('voucher_no'),
            'fiscal_year': request.POST.get('fiscal_year'),
            'vendor_id': request.POST.get('party_ledger_id'),
            'date_bs': request.POST.get('date_bs'),
            'date_ad': request.POST.get('date_ad'),
            'reference_no': request.POST.get('party_invoice_no'),
            'purchase_account': request.POST.get('purchase_account_ledger_id'),
            'payment_mode': request.POST.get('payment_mode'),
            'agent_id': request.POST.get('agent_id'),
            'area_id': request.POST.get('agent_area_id'),
            'due_days': request.POST.get('due_days'),
            'order_reference': request.POST.get('order_reference_id'),
            'narration': request.POST.get('narration'),
            'line_items': [],
            'header_discount': {
                'value': request.POST.get('hdr_discount_value', 0),
                'type': request.POST.get('hdr_discount_type', 'amount')
            },
            'bill_rounding': request.POST.get('bill_rounding', 0),
        }
        
        # Parse line items
        item_ids = [key for key in request.POST.keys() if key.endswith('-item_id') and key.startswith('lines-')]
        for item_key in item_ids:
            index = item_key.split('-')[1]
            line_item = {
                'item_id': request.POST.get(f'lines-{index}-item_id'),
                'hs_code': request.POST.get(f'lines-{index}-hs_code'),
                'description': request.POST.get(f'lines-{index}-description'),
                'quantity': request.POST.get(f'lines-{index}-qty', 0),
                'unit': request.POST.get(f'lines-{index}-unit_id'),
                'godown': request.POST.get(f'lines-{index}-godown_id'),
                'rate': request.POST.get(f'lines-{index}-rate', 0),
                'vat_applicable': request.POST.get(f'lines-{index}-vat_applicable') == 'yes',
                'discount_type': request.POST.get(f'lines-{index}-discount_type', 'none'),
                'discount_value': request.POST.get(f'lines-{index}-discount_value', 0),
            }
            data['line_items'].append(line_item)

        # Import the purchase invoice service
        from accounting.services.purchase_invoice_service import PurchaseInvoiceService

        # Validate data
        errors = ValidationService.validate_purchase_invoice_data(organization, data)
        if errors:
            return JsonResponse({'success': False, 'errors': errors})

        # Create invoice
        invoice = PurchaseInvoiceService.create_invoice(organization, data, request.user)

        # Send notifications if needed
        if invoice.amount > 100000:  # High value threshold
            NotificationService.send_approval_notification(
                invoice.id, invoice.get_approvers(), 'purchase_invoice'
            )

        return JsonResponse({
            'success': True,
            'invoice_id': invoice.id,
            'message': 'Invoice saved successfully'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def apply_purchase_order(request, order_id):
    """Apply purchase order lines to invoice"""
    if request.method == 'POST':
        order_id = request.POST.get('order_reference_id')
    
    try:
        organization = request.user.get_active_organization()

        # Import the purchase invoice service (we'll need to create this)
        from accounting.services.purchase_invoice_service import PurchaseInvoiceService

        order_lines = PurchaseInvoiceService.get_order_lines_for_invoice(organization, order_id)
        return JsonResponse({'success': True, 'lines': order_lines})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def get_next_voucher_number(request):
    """Get next voucher number"""
    try:
        organization = request.user.get_active_organization()
        next_no = DocumentSequenceService.get_next_number(organization, 'purchase_invoice', 'PB')
        return JsonResponse({'success': True, 'voucher_no': next_no})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
