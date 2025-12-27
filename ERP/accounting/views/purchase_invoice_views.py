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
from utils.date_field_utils import configure_form_date_fields
from utils.calendars import maybe_coerce_bs_date
from django.utils.dateparse import parse_date
from datetime import datetime
import logging
from django.conf import settings
logger = logging.getLogger(__name__)


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
    can_post_invoice = (
        request.user.has_perm('accounting.post_purchase_invoice') or
        request.user.has_perm('purchasing.post_purchase_invoice')
    )

    def _mark_empty_purchase_lines_for_delete(data, prefix="items"):
        """Auto-mark truly empty item rows so validation doesn't drop PO-applied lines.

        A row is considered empty if it has no product, no description, and zero/blank qty+rate.
        """
        try:
            total = int(data.get(f"{prefix}-TOTAL_FORMS", "0"))
        except Exception:
            total = 0
        for idx in range(total):
            prod = (data.get(f"{prefix}-{idx}-product") or "").strip()
            desc = (data.get(f"{prefix}-{idx}-description") or "").strip()
            qty = data.get(f"{prefix}-{idx}-quantity")
            rate = data.get(f"{prefix}-{idx}-unit_cost")
            if prod or desc:
                continue
            # Treat missing/zero qty + rate as empty
            def _is_blank_num(val):
                if val in (None, "", "0", "0.0", "0.00"):
                    return True
                try:
                    return float(val) == 0
                except Exception:
                    return False
            if _is_blank_num(qty) and _is_blank_num(rate):
                data[f"{prefix}-{idx}-DELETE"] = "on"
        return data

    def _relax_validation_for_deleted_forms(formset):
        """Ensure forms marked for deletion don't block validation."""
        if not formset:
            return
        for idx, form in enumerate(formset.forms):
            # Ensure cleaned_data exists to satisfy Django's delete check even if form isn't validated yet
            if not hasattr(form, "cleaned_data"):
                form.cleaned_data = {}
            try:
                delete_val = form.data.get(f"{form.prefix}-DELETE") or form.data.get(f"{formset.prefix}-{idx}-DELETE")
            except Exception:
                delete_val = None
            if str(delete_val).lower() in ('on', 'true', '1', 'yes'):
                form.empty_permitted = True
                form._errors = {}
        return formset

    def _has_non_deleted_lines(data, prefix="items"):
        """Return True if any line has content and is not marked for delete."""
        try:
            total = int(data.get(f"{prefix}-TOTAL_FORMS", "0"))
        except Exception:
            total = 0
        for idx in range(total):
            if data.get(f"{prefix}-{idx}-DELETE"):
                continue
            if (
                (data.get(f"{prefix}-{idx}-product") or "").strip()
                or (data.get(f"{prefix}-{idx}-description") or "").strip()
                or (data.get(f"{prefix}-{idx}-quantity") not in (None, "", "0", "0.0", "0.00"))
                or (data.get(f"{prefix}-{idx}-unit_cost") not in (None, "", "0", "0.0", "0.00"))
            ):
                return True
        return False

    def _build_payment_formset(data=None, invoice_date=None):
        account_choices, cash_bank_accounts = _get_cash_bank_choices(organization)
        PaymentFormSet = formset_factory(PurchasePaymentForm, extra=0, can_delete=True)
        form_kwargs = {
            'invoice_date': invoice_date,
            'cash_bank_choices': account_choices,
            'organization': organization,
        }
        if data is None:
            return PaymentFormSet(prefix='payments', form_kwargs=form_kwargs), cash_bank_accounts, account_choices
        return PaymentFormSet(data, prefix='payments', form_kwargs=form_kwargs), cash_bank_accounts, account_choices

    if request.method == 'GET':
        form = PurchaseInvoiceForm(organization=organization)
        configure_form_date_fields(form, organization=organization)
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
            'can_post_invoice': can_post_invoice,
        }
        return render(request, 'accounting/purchase/new_enhanced.html', context)
    
    elif request.method == 'POST':
        # Make a mutable copy of POST so we can coerce BS or non-ISO AD dates
        data = request.POST.copy()
        # Ensure organization is present in POST so the ModelForm doesn't require it
        try:
            if not data.get('organization'):
                data['organization'] = str(getattr(organization, 'id', getattr(organization, 'pk', '')))
        except Exception:
            data['organization'] = ''

        # Auto-mark placeholder/blank item rows for deletion so PO-imported lines stay intact
        data = _mark_empty_purchase_lines_for_delete(data, prefix="items")

        # If no usable lines exist yet but an order reference is present, auto-import lines
        order_ref = (
            data.get('order_reference')
            or data.get('purchase_order')
            or data.get('order_reference_id')
            or data.get('purchase_order_id')
        )
        if order_ref and not _has_non_deleted_lines(data, prefix="items"):
            try:
                from accounting.services.order_import_service import import_purchase_order_lines
                imported = import_purchase_order_lines(organization, order_ref)
            except Exception:
                imported = []
            try:
                total = int(data.get("items-TOTAL_FORMS", "0") or 0)
            except Exception:
                total = 0
            for offset, item in enumerate(imported):
                idx = total + offset
                data[f"items-{idx}-product"] = item.get("product_id") or ""
                data[f"items-{idx}-product_code"] = item.get("product_code") or ""
                data[f"items-{idx}-description"] = item.get("description") or ""
                data[f"items-{idx}-quantity"] = item.get("quantity") or ""
                data[f"items-{idx}-unit_cost"] = item.get("unit_cost") or ""
                data[f"items-{idx}-unit_display"] = item.get("unit") or ""
                data[f"items-{idx}-warehouse"] = item.get("godown") or ""
                data[f"items-{idx}-vat_rate"] = item.get("vat_rate") or ""
                data[f"items-{idx}-input_vat_account"] = item.get("input_vat_account") or ""
                data[f"items-{idx}-account"] = item.get("account_id") or ""
                data[f"items-{idx}-po_reference"] = item.get("po_line_id") or item.get("po_reference") or ""
            data["items-TOTAL_FORMS"] = str(total + len(imported))

        def _coerce_field(post_dict, name):
            # If AD value already present, leave it
            if post_dict.get(name):
                return
            # Prefer BS companion field
            bs_key = f"{name}_bs"
            raw = post_dict.get(bs_key) or post_dict.get(f"{name}-bs")
            if raw:
                coerced = maybe_coerce_bs_date(str(raw))
                if coerced:
                    post_dict[name] = coerced.isoformat()
                    return
            # Try common AD formats
            raw = post_dict.get(name) or raw
            if raw:
                s = str(raw).strip()
                # Try parse_date first (ISO-ish)
                pd = parse_date(s)
                if pd:
                    post_dict[name] = pd.isoformat()
                    return
                # Try common US/UK formats
                for fmt in ('%m/%d/%Y', '%d-%m-%Y', '%d/%m/%Y'):
                    try:
                        dt = datetime.strptime(s, fmt).date()
                        post_dict[name] = dt.isoformat()
                        return
                    except Exception:
                        continue

        def _parse_invoice_date(data):
            # first try the AD field
            raw = data.get('invoice_date')
            if raw:
                date_field = forms.DateField(required=False)
                try:
                    return date_field.clean(raw)
                except ValidationError:
                    pass
            # fall back to BS field
            bs_raw = data.get('invoice_date_bs')
            if bs_raw:
                return maybe_coerce_bs_date(bs_raw)
            return None

        _coerce_field(data, 'invoice_date')
        _coerce_field(data, 'due_date')

        # Debug: log keys present in data before validation
        logger.debug('PurchaseInvoice POST keys before validation: %s', list(data.keys()))
        form = PurchaseInvoiceForm(data, organization=organization)
        configure_form_date_fields(form, organization=organization)

        form_valid = form.is_valid()
        invoice_date_value = form.cleaned_data.get('invoice_date')
        payments_formset, cash_bank_accounts, _ = _build_payment_formset(
            data,
            invoice_date=invoice_date_value,
        )

        # Populate missing line descriptions from product master when possible
        try:
            from inventory.models import Product
            total_forms = int(data.get('items-TOTAL_FORMS', '0') or 0)
            for i in range(total_forms):
                prod_key = f'items-{i}-product'
                desc_key = f'items-{i}-description'
                unit_display_key = f'items-{i}-unit_display'
                unit_cost_key = f'items-{i}-unit_cost'
                prod_val = data.get(prod_key)
                desc_val = data.get(desc_key)
                if prod_val and (not desc_val or str(desc_val).strip() == ''):
                    try:
                        pid = int(prod_val)
                    except Exception:
                        pid = None
                    if pid:
                        prod = Product.objects.filter(pk=pid, organization=organization).first()
                        if prod:
                            data[desc_key] = prod.description or prod.name
                            # populate unit display if missing
                            try:
                                if prod.base_unit and not data.get(unit_display_key):
                                    data[unit_display_key] = prod.base_unit.name or ''
                            except Exception:
                                pass
                            # populate unit cost if missing or zero
                            try:
                                if (not data.get(unit_cost_key) or str(data.get(unit_cost_key)).strip() == '0') and prod.cost_price:
                                    data[unit_cost_key] = str(prod.cost_price)
                            except Exception:
                                pass
        except Exception:
            logger.exception('Failed to auto-populate product descriptions')

        invoice_stub = PurchaseInvoice(organization=organization)
        line_formset = PurchaseInvoiceLineFormSet(
            data,
            prefix='items',
            instance=invoice_stub,
            form_kwargs={'organization': organization},
        )
        _relax_validation_for_deleted_forms(line_formset)

        lines_valid = line_formset.is_valid()
        payments_valid = payments_formset.is_valid()
        calc_totals = {}

        auto_post_requested = False
        if can_post_invoice:
            auto_post_requested = str(request.POST.get('auto_post', '')).lower() in ('on', 'true', '1', 'yes')

        if form_valid and lines_valid and payments_valid:
            # Consider any non-deleted line with cleaned data, even if it matches initial
            # (e.g., lines imported from a PO that haven't been edited yet).
            valid_lines = [
                f for f in line_formset.forms
                if getattr(f, "cleaned_data", None) and not f.cleaned_data.get('DELETE')
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
            calc_source_forms = []
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
                    'vat_rate': vat_rate,
                    'row_discount_value': line_form.cleaned_data.get('discount_amount') or 0,
                    'row_discount_type': 'amount',
                })
                calc_source_forms.append(line_form)
                product = line_form.cleaned_data.get('product')
                warehouse = line_form.cleaned_data.get('warehouse')
                validation_line = {
                    'quantity': qty,
                    'rate': rate,
                    'transaction_type': 'purchase',
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
            calc_totals = totals.get('totals', {}) or {}
            total_amount = calc_totals.get('grand_total') or Decimal('0')
            calc_rows = totals.get('rows', []) or []
            for idx, row in enumerate(calc_rows):
                try:
                    calc_source_forms[idx].cleaned_data['tax_amount'] = row.get('vat_amount') or Decimal('0')
                except Exception:
                    continue

            payment_sum = _sum_payment_amounts(payments_formset)
            if payment_sum > total_amount:
                form.add_error(None, 'Payment total exceeds invoice total.')
                form_valid = False

            if form_valid:
                try:
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
                except Exception as exc:
                    form.add_error(None, f"Validation failed: {exc}")
                    form_valid = False

        if form_valid and lines_valid and payments_valid:
            try:
                with transaction.atomic():
                    invoice = form.save(commit=False)
                    invoice.organization = organization
                    invoice.created_by = request.user
                    invoice.invoice_date = form.cleaned_data.get('invoice_date') or invoice.invoice_date
                    invoice.due_date = form.cleaned_data.get('due_date') or invoice.due_date
                    invoice.invoice_date_bs = form.cleaned_data.get('invoice_date_bs') or invoice.invoice_date_bs
                    invoice.rounding_adjustment = Decimal(str(bill_rounding or 0)).quantize(Decimal('0.01'))
                    invoice.discount_amount = Decimal(
                        calc_totals.get('header_discount') or Decimal('0')
                    ).quantize(Decimal('0.01'))
                    if header_discount_type == 'percent':
                        invoice.discount_percentage = Decimal(str(header_discount_value or 0))
                    else:
                        invoice.discount_percentage = Decimal('0')
                    vendor_obj = form.cleaned_data.get('vendor')
                    if vendor_obj:
                        invoice.vendor_display_name = (
                            getattr(vendor_obj, 'display_name', None)
                            or getattr(vendor_obj, 'name', None)
                            or str(vendor_obj)
                        )
                    agent_area_id = request.POST.get('agent_area_id')
                    if agent_area_id:
                        from accounting.models import Area
                        area = Area.objects.filter(organization=organization, area_id=agent_area_id).first()
                        invoice.agent_area = area.name if area else str(agent_area_id)
                    invoice.save()

                    # Re-bind line formset with actual invoice for saving (use coerced/augmented data)
                    line_formset = PurchaseInvoiceLineFormSet(
                        data,
                        prefix='items',
                        instance=invoice,
                        form_kwargs={'organization': organization},
                    )
                    _relax_validation_for_deleted_forms(line_formset)
                    if line_formset.is_valid():
                        # Save lines
                        line_objects = line_formset.save(commit=False)
                        # Fallback: if line account is missing, default to header purchase account
                        header_account = form.cleaned_data.get('purchase_account')
                        header_account_id = getattr(header_account, 'pk', None) or header_account
                        for i, obj in enumerate(line_objects, start=1):
                            obj.line_number = i
                            obj.invoice = invoice
                            if not getattr(obj, 'account_id', None) and header_account_id:
                                obj.account_id = header_account_id
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

                    # Recompute totals from persisted lines to keep GL/posting in sync
                    invoice.recompute_totals(save=True)

                    posted_invoice = None
                    auto_post_error = None
                    if auto_post_requested:
                        try:
                            from purchasing.services.procurement import post_purchase_invoice
                            posted_invoice = post_purchase_invoice(invoice)
                        except Exception as exc:
                            auto_post_error = str(exc)
                            logger.exception("Auto-post purchase invoice failed: %s", exc)

                    # Success
                    success_form = PurchaseInvoiceForm(organization=organization)
                    configure_form_date_fields(success_form, organization=organization)
                    empty_line_formset = PurchaseInvoiceLineFormSet(prefix='items', form_kwargs={'organization': organization})
                    invoice_date = timezone.now().date()
                    empty_payments_formset, cash_bank_accounts, _ = _build_payment_formset(invoice_date=invoice_date)
                    success_message = 'Purchase Invoice created successfully.'
                    if posted_invoice:
                        success_message = 'Purchase Invoice created and posted successfully.'
                    elif auto_post_error:
                        success_message = f'Invoice saved, but auto-post failed: {auto_post_error}'
                    context = {
                        'form': success_form,
                        'line_items': PurchaseInvoiceLine.objects.none(),
                        'line_formset': empty_line_formset,
                        'payments_formset': empty_payments_formset,
                        'cash_bank_accounts': cash_bank_accounts,
                        'agents': AgentService.get_agents_for_dropdown(organization),
                        'areas': AgentService.get_areas_for_dropdown(organization),
                        'alert_message': success_message,
                        'alert_level': 'success' if not auto_post_error else 'warning',
                        'can_post_invoice': can_post_invoice,
                    }
                    template_name = 'accounting/purchase/_purchase_form_panel.html' if _is_htmx(request) else 'accounting/purchase/new_enhanced.html'
                    response = render(request, template_name, context)
                    if _is_htmx(request):
                        response['HX-Trigger'] = 'purchaseInvoiceSaved'
                    return response
            except Exception as e:
                form.add_error(None, f"Error saving invoice: {str(e)}")

        # Re-display form with errors
        line_items = PurchaseInvoiceLine.objects.none()
        # Log detailed debug info to help trace why validation failed
        try:
            if not form_valid:
                logger.error("Purchase invoice form invalid: %s", getattr(form, 'errors', None))
            if not lines_valid:
                logger.error("Purchase invoice lines invalid: %s", getattr(line_formset, 'errors', None))
            if not payments_valid:
                logger.error("Purchase invoice payments invalid: %s", getattr(payments_formset, 'errors', None))
            # Also log coerced date values from posted data (if available)
            try:
                posted_invoice = (request.POST.get('invoice_date') or request.POST.get('invoice_date_bs') or request.POST.get('invoice_date_ad'))
                posted_due = (request.POST.get('due_date') or request.POST.get('due_date_bs') or request.POST.get('due_date_ad'))
                logger.debug('Posted invoice_date raw=%s coerced=%s', posted_invoice, invoice_date_value)
                logger.debug('Posted due_date raw=%s', posted_due)
            except Exception:
                logger.exception('Error while logging posted dates')
        except Exception:
            logger.exception('Error while logging purchase invoice validation details')
        context = {
            'form': form,
            'line_items': line_items,
            'line_formset': line_formset,
            'payments_formset': payments_formset,
            'cash_bank_accounts': cash_bank_accounts,
            'agents': AgentService.get_agents_for_dropdown(organization),
            'areas': AgentService.get_areas_for_dropdown(organization),
            'alert_message': 'Please correct the errors highlighted in the form.',
            'alert_level': 'danger',
            'can_post_invoice': can_post_invoice,
            'debug_info': {
                'form_errors': getattr(form, 'errors', None),
                'line_errors': getattr(line_formset, 'errors', None),
                'payment_errors': getattr(payments_formset, 'errors', None),
            },
        }
        status = 422
        template_name = 'accounting/purchase/_purchase_form_panel.html' if _is_htmx(request) else 'accounting/purchase/new_enhanced.html'
        response = render(request, template_name, context, status=status)
        if _is_htmx(request):
            response['HX-Trigger'] = 'purchaseInvoiceSaveFailed'
        return response


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
    post_data = request.POST.copy()
    # Drop placeholder blank lines so totals aren't skewed and imports remain
    try:
        total_forms = int(post_data.get(f'{prefix_val}-TOTAL_FORMS', '0'))
    except Exception:
        total_forms = 0
    for idx in range(total_forms):
        prod = (post_data.get(f"{prefix_val}-{idx}-product") or "").strip()
        desc = (post_data.get(f"{prefix_val}-{idx}-description") or "").strip()
        qty = post_data.get(f"{prefix_val}-{idx}-quantity")
        rate = post_data.get(f"{prefix_val}-{idx}-unit_cost")
        def _is_blank_num(val):
            if val in (None, "", "0", "0.0", "0.00"):
                return True
            try:
                return float(val) == 0
            except Exception:
                return False
        if not prod and not desc and _is_blank_num(qty) and _is_blank_num(rate):
            post_data[f"{prefix_val}-{idx}-DELETE"] = "on"
    header_form = PurchaseInvoiceForm(data=post_data, organization=organization)
    PurchaseInvoiceLineFormSet_local = forms.formset_factory(PurchaseInvoiceLineForm, can_delete=True)
    line_formset = PurchaseInvoiceLineFormSet_local(data=post_data, prefix=prefix_val)

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
            organization=organization,
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
    prefix = request.POST.get('prefix') or request.GET.get('prefix') or 'items'
    form_count = (
        request.POST.get('form_count')
        or request.GET.get('form_count')
        or request.POST.get(f'{prefix}-TOTAL_FORMS')
        or request.GET.get(f'{prefix}-TOTAL_FORMS')
        or '0'
    )
    variant = request.POST.get('variant') or request.GET.get('variant') or 'default'
    try:
        start_index = int(form_count)
    except Exception:
        start_index = 0

    imported = []
    if order_ref:
        from accounting.services.order_import_service import import_purchase_order_lines
        imported = import_purchase_order_lines(organization, order_ref)

    forms = []
    new_total = start_index
    for idx, item in enumerate(imported):
        fi = start_index + idx
        from accounting.forms import PurchaseInvoiceLineForm
        form_prefix = f"{prefix}-{fi}"
        form = PurchaseInvoiceLineForm(prefix=form_prefix, organization=organization)
        initial_vals = {
            'product': item.get('product_id'),
            'product_code': item.get('product_code'),
            'description': item.get('description', ''),
            'quantity': item.get('quantity', 0),
            'unit_cost': item.get('unit_cost', 0),
            'unit_display': item.get('unit'),
            'warehouse': item.get('godown'),
            'vat_rate': item.get('vat_rate'),
            'input_vat_account': item.get('input_vat_account'),
            'account': item.get('account_id'),
            'po_reference': item.get('po_line_id') or item.get('po_reference'),
        }
        form.initial.update({k: v for k, v in initial_vals.items() if v is not None})
        forms.append({'form': form, 'form_index': fi})
        new_total += 1

    context = {
        'import_forms': forms,
        'prefix': prefix,
        'new_total': new_total,
        'variant': variant,
    }
    # Return partial with rows and an auto-triggered recalc loader
    template_name = 'accounting/partials/_purchase_import_rows_and_recalc.html'
    if variant == 'enhanced':
        template_name = 'accounting/purchase/_purchase_import_rows_and_recalc_new.html'
    return render(request, template_name, context)


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

    vendor = None
    vendor_outstanding = None
    projected_outstanding = None
    try:
        vendor_id = request.POST.get('vendor') or request.POST.get('supplier')
        if vendor_id:
            vendor = Vendor.objects.get(pk=vendor_id, organization=organization)
            vendor_outstanding = vendor.recompute_outstanding_balance()
            projected_outstanding = (vendor_outstanding or Decimal('0')) + remaining
    except Exception:
        vendor = None

    context = {
        'payment_formset': payment_formset,
        'remaining': remaining,
        'totals': result['totals'],
        'vendor': vendor,
        'vendor_outstanding': vendor_outstanding,
        'projected_outstanding': projected_outstanding,
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

    balance = None
    outstanding = None
    last_invoice = None
    credit_limit = None
    available_credit = None
    if vendor:
        outstanding = vendor.recompute_outstanding_balance()
        balance = outstanding
        credit_limit = vendor.credit_limit
        if credit_limit is not None:
            available_credit = credit_limit - outstanding
        last_invoice = (
            PurchaseInvoice.objects.filter(organization=organization, vendor=vendor).order_by('-invoice_date').first()
        )

    context = {
        'vendor': vendor,
        'balance': balance,
        'outstanding': outstanding,
        'last_invoice': last_invoice,
        'credit_limit': credit_limit,
        'available_credit': available_credit,
    }
    response = render(request, 'accounting/partials/_supplier_summary_panel.html', context)
    # Also update the header credit banner via OOB swap
    oob = render(request, 'accounting/partials/_vendor_credit_banner.html', context)
    response.content += oob.content
    return response
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
                payment_mode=form.cleaned_data.get("payment_mode") or "credit",
                metadata=getattr(form.instance, "metadata", {}) or {},
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
