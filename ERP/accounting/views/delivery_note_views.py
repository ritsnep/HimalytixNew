from decimal import Decimal
import json

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.forms import inlineformset_factory
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, DetailView

from accounting.forms.commerce_forms import DeliveryNoteForm, DeliveryNoteLineForm
from accounting.mixins import PermissionRequiredMixin
from accounting.models import DeliveryNote, DeliveryNoteLine
from inventory.models import Product, Warehouse


DeliveryNoteLineFormSet = inlineformset_factory(
    DeliveryNote,
    DeliveryNoteLine,
    form=DeliveryNoteLineForm,
    extra=1,
    can_delete=True,
)


class DeliveryNoteListView(PermissionRequiredMixin, ListView):
    model = DeliveryNote
    template_name = "accounting/delivery_note_list.html"
    context_object_name = "delivery_notes"
    permission_required = ("accounting", "deliverynote", "view")

    def get_queryset(self):
        organization = self.get_organization()
        if not organization:
            return DeliveryNote.objects.none()
        return DeliveryNote.objects.filter(organization=organization).order_by("-delivery_date", "-delivery_note_id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["create_url"] = reverse("accounting:delivery_note_create")
        context.setdefault("page_title", "Delivery Notes")
        return context


class DeliveryNoteCreateView(PermissionRequiredMixin, View):
    template_name = "accounting/delivery_note_form.html"
    permission_required = ("accounting", "deliverynote", "add")

    def get(self, request):
        organization = self.get_organization()
        initial_date = timezone.now().date()
        form = DeliveryNoteForm(
            organization=organization,
            initial={"organization": organization, "delivery_date": initial_date},
        )
        formset = DeliveryNoteLineFormSet(prefix="lines", form_kwargs={"organization": organization})
        context = {"form": form, "line_formset": formset, "form_title": "New Delivery Note", "product_data_json": json.dumps(self._serialize_products(organization), default=str)}
        return render(request, self.template_name, context)

    @transaction.atomic
    def post(self, request):
        organization = self.get_organization()
        form = DeliveryNoteForm(data=request.POST, organization=organization)
        formset = DeliveryNoteLineFormSet(request.POST, prefix="lines", form_kwargs={"organization": organization})
        context = {"form": form, "line_formset": formset, "form_title": "New Delivery Note", "product_data_json": json.dumps(self._serialize_products(organization), default=str)}
        if not (form.is_valid() and formset.is_valid()):
            return render(request, self.template_name, context)

        # create delivery note
        note = form.save(commit=False)
        note.organization = organization
        note.customer_display_name = note.customer.display_name if note.customer else note.customer_display_name
        note.save()

        line_payload = []
        for idx, lf in enumerate(formset):
            if not lf.has_changed() or lf.cleaned_data.get("DELETE"):
                continue
            data = lf.cleaned_data
            line = DeliveryNoteLine(
                delivery_note=note,
                line_number=(data.get("line_number") or (idx + 1)),
                description=data.get("description") or "",
                product=data.get("product"),
                product_code=(getattr(data.get("product"), "code", None) or data.get("product_code") or ""),
                quantity=data.get("quantity") or Decimal("0"),
            )
            line.save()
            line_payload.append(line)

        if not line_payload:
            form.add_error(None, "At least one line item is required.")
            return render(request, self.template_name, context)

        # optionally confirm now
        if request.POST.get("action") == "confirm":
            try:
                note.confirm(user=request.user)
                messages.success(request, f"Delivery note {note.note_number or note.delivery_note_id} confirmed and stock updated.")
            except ValidationError as exc:
                transaction.set_rollback(True)
                form.add_error(None, exc)
                return render(request, self.template_name, context)
        else:
            messages.success(request, "Delivery note saved as draft.")

        return redirect(reverse("accounting:delivery_note_list"))

    def _serialize_products(self, organization):
        products = Product.objects.filter(organization=organization)
        return [{"code": p.code, "name": p.name, "is_inventory_item": p.is_inventory_item} for p in products]


class DeliveryNotePrintView(PermissionRequiredMixin, DetailView):
    model = DeliveryNote
    template_name = "accounting/print/delivery_note_a4.html"
    pk_url_kwarg = 'pk'
    permission_required = ("accounting", "deliverynote", "view")

    def get_object(self):
        return DeliveryNote.objects.select_related('customer', 'warehouse').prefetch_related('lines').get(pk=self.kwargs.get('pk'))


class DeliveryNoteInvoiceCreateView(PermissionRequiredMixin, View):
    permission_required = ("accounting", "deliverynote", "add")

    def post(self, request, pk):
        # Create a SalesInvoice from a confirmed DeliveryNote
        from accounting.services.sales_invoice_service import SalesInvoiceService
        from accounting.models import SalesInvoice

        note = DeliveryNote.objects.prefetch_related('lines').get(pk=pk)
        if note.status != 'confirmed':
            return render(request, 'accounting/delivery_note_invoice_error.html', {
                'message': 'Delivery note must be confirmed before invoicing.',
                'object': note,
            })

        organization = note.organization
        invoice_date = timezone.localdate()
        currency = getattr(note.customer, 'default_currency', None) or organization.base_currency_code_id
        currency_obj = None
        from accounting.models import Currency
        if currency:
            currency_obj = Currency.objects.filter(currency_code=currency).first()

        # Build lines from delivery note
        lines = []
        for line in note.lines.all():
            unit_price = 0
            product = getattr(line, 'product', None)
            if product:
                unit_price = getattr(product, 'sale_price', 0)
            lines.append({
                'description': line.description or (product.name if product else ''),
                'product_code': getattr(product, 'code', '') if product else line.product_code,
                'quantity': line.quantity,
                'unit_price': unit_price,
                'discount_amount': 0,
                'revenue_account': getattr(product, 'income_account', None) if product else None,
                'tax_code': None,
                'tax_amount': 0,
            })

        service = SalesInvoiceService(request.user)
        try:
            invoice = service.create_invoice(
                organization=organization,
                customer=note.customer,
                invoice_date=invoice_date,
                currency=currency_obj or (Currency.objects.first() if Currency.objects.exists() else None),
                lines=lines,
                metadata={'source': 'delivery_note', 'delivery_note_id': note.pk},
            )
            # Link delivery note to invoice to prevent double-billing
            note.linked_invoice = invoice
            note.save(update_fields=['linked_invoice'])
            return redirect(reverse('accounting:sales_invoice_detail', args=[invoice.invoice_id]))
        except Exception as exc:
            return render(request, 'accounting/delivery_note_invoice_error.html', {
                'message': str(exc),
                'object': note,
            })