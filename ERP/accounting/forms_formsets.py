"""
Formset definitions for accounting forms
"""
from django.forms import inlineformset_factory
from accounting.models import PurchaseInvoice, PurchaseInvoiceLine, APPayment
from accounting.forms import PurchaseInvoiceLineForm, PurchasePaymentForm


# Formset definitions for purchase invoices
PurchaseInvoiceLineFormSet = inlineformset_factory(
    PurchaseInvoice,
    PurchaseInvoiceLine,
    form=PurchaseInvoiceLineForm,
    extra=1,
    can_delete=True,
)

PurchasePaymentFormSet = inlineformset_factory(
    PurchaseInvoice,
    APPayment,
    form=PurchasePaymentForm,
    extra=1,
    can_delete=True,
)
