from django.contrib import messages
from django.forms import inlineformset_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from accounting.forms import (
    APPaymentForm,
    APPaymentLineForm,
    CustomerForm,
    VendorForm,
)
from accounting.mixins import PermissionRequiredMixin, UserOrganizationMixin
from accounting.models import APPayment, APPaymentLine, Customer, Vendor


APPaymentLineFormSet = inlineformset_factory(
    APPayment,
    APPaymentLine,
    form=APPaymentLineForm,
    extra=1,
    can_delete=True,
)


class CustomerListView(PermissionRequiredMixin, UserOrganizationMixin, ListView):
    model = Customer
    template_name = "accounting/customer_list.html"
    context_object_name = "customers"
    permission_required = ("accounting", "customer", "view")

    def get_queryset(self):
        organization = self.get_organization()
        if not organization:
            return Customer.objects.none()
        return Customer.objects.filter(organization=organization).order_by("display_name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["create_url"] = reverse("accounting:customer_create")
        context["create_button_text"] = "New Customer"
        context.setdefault("page_title", "Customers")
        return context


class CustomerFormMixin(UserOrganizationMixin):
    form_class = CustomerForm
    template_name = "accounting/customer_form.html"
    success_url = reverse_lazy("accounting:customer_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.get_organization()
        return kwargs

    def form_valid(self, form):
        organization = self.get_organization()
        if organization:
            form.instance.organization = organization
        user = self.request.user
        if not form.instance.pk:
            form.instance.created_by = user
        form.instance.updated_by = user
        response = super().form_valid(form)
        messages.success(self.request, "Customer saved successfully.")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("back_url", "accounting:customer_list")
        return context


class CustomerCreateView(PermissionRequiredMixin, CustomerFormMixin, CreateView):
    permission_required = ("accounting", "customer", "add")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("form_title", "Create Customer")
        return context


class CustomerUpdateView(PermissionRequiredMixin, CustomerFormMixin, UpdateView):
    permission_required = ("accounting", "customer", "change")

    def get_queryset(self):
        organization = self.get_organization()
        if not organization:
            return Customer.objects.none()
        return Customer.objects.filter(organization=organization)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("form_title", "Edit Customer")
        return context


class VendorListView(PermissionRequiredMixin, UserOrganizationMixin, ListView):
    model = Vendor
    template_name = "accounting/vendor_list.html"
    context_object_name = "vendors"
    permission_required = ("accounting", "vendor", "view")

    def get_queryset(self):
        organization = self.get_organization()
        if not organization:
            return Vendor.objects.none()
        return Vendor.objects.filter(organization=organization).order_by("display_name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["create_url"] = reverse("accounting:vendor_create")
        context["create_button_text"] = "New Vendor"
        context.setdefault("page_title", "Vendors")
        return context


class VendorFormMixin(UserOrganizationMixin):
    form_class = VendorForm
    template_name = "accounting/vendor_form.html"
    success_url = reverse_lazy("accounting:vendor_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.get_organization()
        return kwargs

    def form_valid(self, form):
        organization = self.get_organization()
        if organization:
            form.instance.organization = organization
        user = self.request.user
        if not form.instance.pk:
            form.instance.created_by = user
        form.instance.updated_by = user
        response = super().form_valid(form)
        messages.success(self.request, "Vendor saved successfully.")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("back_url", "accounting:vendor_list")
        return context


class VendorCreateView(PermissionRequiredMixin, VendorFormMixin, CreateView):
    permission_required = ("accounting", "vendor", "add")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("form_title", "Create Vendor")
        return context


class VendorUpdateView(PermissionRequiredMixin, VendorFormMixin, UpdateView):
    permission_required = ("accounting", "vendor", "change")

    def get_queryset(self):
        organization = self.get_organization()
        if not organization:
            return Vendor.objects.none()
        return Vendor.objects.filter(organization=organization)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("form_title", "Edit Vendor")
        return context


class APPaymentListView(PermissionRequiredMixin, UserOrganizationMixin, ListView):
    model = APPayment
    template_name = "accounting/ap_payment_list.html"
    context_object_name = "payments"
    permission_required = ("accounting", "appayment", "view")

    def get_queryset(self):
        organization = self.get_organization()
        if not organization:
            return APPayment.objects.none()
        return APPayment.objects.filter(organization=organization).select_related("vendor")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["create_url"] = reverse("accounting:ap_payment_create")
        context["create_button_text"] = "New AP Payment"
        context.setdefault("page_title", "AP Payments")
        return context


class APPaymentFormView(PermissionRequiredMixin, UserOrganizationMixin, View):
    template_name = "accounting/ap_payment_form.html"
    form_class = APPaymentForm
    success_message = "Payment saved successfully."
    form_title = "AP Payment"
    permission_required = ("accounting", "appayment", "add")

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().dispatch(request, *args, **kwargs)

    def get_object(self):
        pk = self.kwargs.get("pk")
        if not pk:
            return None
        organization = self.get_organization()
        return get_object_or_404(APPayment, pk=pk, organization=organization)

    def get(self, request, *args, **kwargs):
        form = self.get_form()
        formset = self.get_formset(form)
        return self.render_to_response(form, formset)

    def post(self, request, *args, **kwargs):
        form = self.get_form(data=request.POST)
        formset = self.get_formset(form, data=request.POST)
        if form.is_valid() and formset.is_valid():
            return self.form_valid(form, formset)
        return self.render_to_response(form, formset)

    def get_form_kwargs(self):
        kwargs = {
            "organization": self.get_organization(),
        }
        if self.object:
            kwargs["instance"] = self.object
        return kwargs

    def get_form(self, data=None):
        kwargs = self.get_form_kwargs()
        if data is not None:
            kwargs["data"] = data
        return self.form_class(**kwargs)

    def get_formset(self, form, data=None):
        organization = self.get_organization()
        vendor = self._resolve_vendor(form)
        kwargs = {
            "instance": self.object,
            "prefix": "lines",
            "form_kwargs": {"organization": organization, "vendor": vendor},
        }
        if data is not None:
            kwargs["data"] = data
        return APPaymentLineFormSet(**kwargs)

    def _resolve_vendor(self, form):
        organization = self.get_organization()
        vendor_id = None
        if form.is_bound:
            vendor_id = form.data.get("vendor")
        elif form.instance and form.instance.pk:
            vendor_id = form.instance.vendor_id
        if vendor_id and organization:
            try:
                return Vendor.objects.get(pk=vendor_id, organization=organization)
            except Vendor.DoesNotExist:
                return None
        if self.object:
            return self.object.vendor
        return None

    def form_valid(self, form, formset):
        organization = self.get_organization()
        payment = form.save(commit=False)
        if organization:
            payment.organization = organization
        user = self.request.user
        if not payment.pk:
            payment.created_by = user
        payment.updated_by = user
        payment.save()
        self.object = payment

        lines = formset.save(commit=False)
        for deleted in formset.deleted_objects:
            deleted.delete()
        for line in lines:
            line.payment = payment
            line.save()

        messages.success(self.request, self.success_message)
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse("accounting:ap_payment_list")

    def render_to_response(self, form, formset):
        context = {
            "form": form,
            "formset": formset,
            "back_url": "accounting:ap_payment_list",
            "form_title": self.form_title,
        }
        return render(self.request, self.template_name, context)


class APPaymentCreateView(APPaymentFormView):
    form_title = "Create AP Payment"
    permission_required = ("accounting", "appayment", "add")


class APPaymentUpdateView(APPaymentFormView):
    form_title = "Edit AP Payment"
    permission_required = ("accounting", "appayment", "change")
