from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, ListView
from django.template.loader import render_to_string

from accounting.forms import QuotationForm, QuotationLineForm
from accounting.mixins import PermissionRequiredMixin
from accounting.models import Quotation, QuotationLine
from accounting.services.quotation_service import QuotationService


QuotationLineFormSet = inlineformset_factory(
    Quotation,
    QuotationLine,
    form=QuotationLineForm,
    extra=1,
    can_delete=True,
)


class QuotationListView(PermissionRequiredMixin, ListView):
    model = Quotation
    template_name = 'accounting/quotation_list.html'
    context_object_name = 'quotations'
    permission_required = ('accounting', 'quotation', 'view')

    def get_queryset(self):
        organization = self.get_organization()
        if not organization:
            return Quotation.objects.none()
        return (
            Quotation.objects
            .filter(organization=organization)
            .select_related('customer')
            .order_by('-quotation_date', '-quotation_id')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse('accounting:quotation_create')
        context['create_button_text'] = 'New Quotation'
        context.setdefault('page_title', 'Quotations')
        return context


class QuotationCreateView(PermissionRequiredMixin, View):
    template_name = 'accounting/quotation_form.html'
    permission_required = ('accounting', 'quotation', 'add')

    def get(self, request):
        organization = self.get_organization()
        form = QuotationForm(organization=organization, initial={'organization': organization})
        formset = QuotationLineFormSet(prefix='lines')
        context = self._build_context(form, formset)
        return render(request, self.template_name, context)

    def post(self, request):
        organization = self.get_organization()
        form = QuotationForm(data=request.POST, organization=organization)
        formset = QuotationLineFormSet(request.POST, prefix='lines')
        context = self._build_context(form, formset)
        if not (form.is_valid() and formset.is_valid()):
            return render(request, self.template_name, context)

        line_payload = []
        for line_form in formset:
            if not line_form.has_changed() or line_form.cleaned_data.get('DELETE'):
                continue
            data = line_form.cleaned_data
            line_payload.append({
                'description': data.get('description'),
                'product_code': data.get('product_code'),
                'quantity': data.get('quantity'),
                'unit_price': data.get('unit_price'),
                'discount_amount': data.get('discount_amount'),
                'revenue_account': data.get('revenue_account'),
                'tax_code': data.get('tax_code'),
                'tax_amount': data.get('tax_amount'),
                'cost_center': data.get('cost_center'),
                'department': data.get('department'),
                'project': data.get('project'),
                'dimension_value': data.get('dimension_value'),
            })

        if not line_payload:
            form.add_error(None, 'At least one line item is required.')
            return render(request, self.template_name, context)

        quote = Quotation.objects.create(
            organization=organization,
            customer=form.cleaned_data['customer'],
            customer_display_name=form.cleaned_data['customer'].display_name,
            quotation_date=form.cleaned_data['quotation_date'],
            valid_until=form.cleaned_data.get('valid_until'),
            due_date=form.cleaned_data.get('due_date'),
            payment_term=form.cleaned_data.get('payment_term'),
            currency=form.cleaned_data['currency'],
            exchange_rate=form.cleaned_data.get('exchange_rate') or Decimal('1'),
            status=form.cleaned_data.get('status', Quotation.STATUS_DRAFT),
            reference_number=form.cleaned_data.get('reference_number', ''),
            terms=form.cleaned_data.get('terms', ''),
            notes=form.cleaned_data.get('notes', ''),
            metadata={},
            created_by=request.user,
            updated_by=request.user,
        )

        for index, payload in enumerate(line_payload, start=1):
            QuotationLine.objects.create(
                quotation=quote,
                line_number=index,
                description=payload.get('description', ''),
                product_code=payload.get('product_code', ''),
                quantity=payload.get('quantity', Decimal('1')),
                unit_price=payload.get('unit_price', Decimal('0')),
                discount_amount=payload.get('discount_amount', Decimal('0')),
                revenue_account=payload.get('revenue_account'),
                tax_code=payload.get('tax_code'),
                tax_amount=payload.get('tax_amount', Decimal('0')),
                cost_center=payload.get('cost_center'),
                department=payload.get('department'),
                project=payload.get('project'),
                dimension_value=payload.get('dimension_value'),
            )
        quote.recompute_totals(save=True)
        messages.success(request, 'Quotation saved.')
        return redirect(reverse('accounting:quotation_detail', args=[quote.pk]))

    def _build_context(self, form, formset):
        return {
            'form': form,
            'formset': formset,
            'line_formset': formset,
            'form_title': 'New Quotation',
            'back_url': 'accounting:quotation_list',
        }


class QuotationUpdateView(PermissionRequiredMixin, View):
    template_name = 'accounting/quotation_form.html'
    permission_required = ('accounting', 'quotation', 'change')

    def get(self, request, pk):
        quote = self._get_quote(pk)
        form = QuotationForm(instance=quote, organization=self.get_organization())
        formset = QuotationLineFormSet(prefix='lines', instance=quote)
        context = self._build_context(form, formset)
        context['form_title'] = 'Edit Quotation'
        return render(request, self.template_name, context)

    def post(self, request, pk):
        quote = self._get_quote(pk)
        form = QuotationForm(data=request.POST, instance=quote, organization=self.get_organization())
        formset = QuotationLineFormSet(request.POST, prefix='lines', instance=quote)
        context = self._build_context(form, formset)
        context['form_title'] = 'Edit Quotation'
        if not (form.is_valid() and formset.is_valid()):
            return render(request, self.template_name, context)

        quote = form.save(commit=False)
        quote.customer_display_name = quote.customer.display_name
        quote.updated_by = request.user
        quote.save()
        formset.save()
        quote.recompute_totals(save=True)
        messages.success(request, 'Quotation updated.')
        return redirect(reverse('accounting:quotation_detail', args=[quote.pk]))

    def _get_quote(self, pk):
        organization = self.get_organization()
        return get_object_or_404(Quotation, pk=pk, organization=organization)

    def _build_context(self, form, formset):
        return {
            'form': form,
            'formset': formset,
            'line_formset': formset,
            'back_url': 'accounting:quotation_list',
        }


class QuotationDetailView(PermissionRequiredMixin, DetailView):
    model = Quotation
    template_name = 'accounting/quotation_detail.html'
    context_object_name = 'quotation'
    permission_required = ('accounting', 'quotation', 'view')

    def get_queryset(self):
        organization = self.get_organization()
        return Quotation.objects.filter(organization=organization)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['lines'] = self.object.lines.order_by('line_number')
        context['convert_url'] = reverse('accounting:quotation_convert', args=[self.object.pk])
        context['status_url'] = reverse('accounting:quotation_status', args=[self.object.pk])
        context['print_pdf_url'] = reverse('accounting:quotation_print', args=[self.object.pk])
        context['can_convert'] = self.object.can_be_converted
        return context


class QuotationStatusUpdateView(PermissionRequiredMixin, View):
    permission_required = ('accounting', 'quotation', 'change')

    def post(self, request, pk):
        quotation = get_object_or_404(
            Quotation,
            pk=pk,
            organization=self.get_organization(),
        )
        action = request.POST.get('status_action')
        service = QuotationService(request.user)
        try:
            if action == 'send':
                service.mark_sent(quotation)
                messages.success(request, 'Quotation marked as sent.')
            elif action == 'accept':
                service.mark_accepted(quotation)
                messages.success(request, 'Quotation marked as accepted.')
            elif action == 'expire':
                service.mark_expired(quotation)
                messages.success(request, 'Quotation marked as expired.')
            else:
                raise ValidationError('Unknown status action.')
        except ValidationError as exc:
            messages.error(request, exc)
        return redirect(reverse('accounting:quotation_detail', args=[quotation.pk]))


class QuotationConvertView(PermissionRequiredMixin, View):
    permission_required = ('accounting', 'quotation', 'change')

    def post(self, request, pk):
        quotation = get_object_or_404(
            Quotation,
            pk=pk,
            organization=self.get_organization(),
        )
        target = request.POST.get('target')
        service = QuotationService(request.user)
        try:
            if target == 'invoice':
                invoice = service.convert_to_invoice(quotation)
                messages.success(request, f'Quotation converted to invoice {invoice.invoice_number}.')
            elif target == 'order':
                order = service.convert_to_sales_order(quotation)
                messages.success(request, f'Quotation converted to sales order {order.order_number}.')
            else:
                raise ValidationError('Conversion target is required.')
        except ValidationError as exc:
            messages.error(request, exc)
        return redirect(reverse('accounting:quotation_detail', args=[quotation.pk]))


class QuotationPrintView(PermissionRequiredMixin, View):
    permission_required = ('accounting', 'quotation', 'view')

    def get(self, request, pk):
        quotation = get_object_or_404(
            Quotation,
            pk=pk,
            organization=self.get_organization(),
        )
        context = {
            'quotation': quotation,
            'organization': quotation.organization,
            'lines': quotation.lines.order_by('line_number'),
            'now': timezone.now(),
        }
        if request.GET.get('format') == 'html':
            return render(request, 'accounting/quotation_print.html', context)

        html = render_to_string('accounting/quotation_print.html', context)
        try:
            from weasyprint import HTML
        except ImportError:
            messages.error(request, 'WeasyPrint must be installed to export quotes as PDF.')
            return redirect(reverse('accounting:quotation_detail', args=[quotation.pk]))

        pdf_buffer = HTML(string=html, base_url=request.build_absolute_uri('/')).write_pdf()
        response = HttpResponse(pdf_buffer, content_type='application/pdf')
        filename = f"Quotation_{quotation.quotation_number or quotation.pk}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
