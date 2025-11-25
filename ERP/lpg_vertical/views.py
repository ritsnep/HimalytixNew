from datetime import date

from django.contrib import messages
from django.shortcuts import render
from django.utils.dateparse import parse_date
from django.views.generic import TemplateView
from rest_framework import permissions, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from lpg_vertical import forms as lpg_forms
from lpg_vertical.models import (
    ConversionRule,
    CylinderSKU,
    CylinderType,
    Dealer,
    InventoryMovement,
    LogisticsTrip,
    LpgProduct,
    NocPurchase,
    SalesInvoice,
    SalesInvoiceLine,
    TransportProvider,
    Vehicle,
)
from lpg_vertical.permissions import (
    LogisticsPermission,
    NocPermission,
    SalesPermission,
)
from lpg_vertical.serializers import (
    ConversionRuleSerializer,
    CylinderSKUSerializer,
    CylinderTypeSerializer,
    DealerSerializer,
    InventoryMovementSerializer,
    LpgProductSerializer,
    LogisticsTripSerializer,
    NocPurchaseSerializer,
    SalesInvoiceSerializer,
    TransportProviderSerializer,
    VehicleSerializer,
)
from lpg_vertical.services import (
    dashboard_summary,
    post_logistics_trip,
    post_noc_purchase,
    post_sales_invoice,
    profit_and_loss,
    revenue_expense_trend,
)


def _get_org(request):
    return getattr(request, "organization", None) or getattr(request.user, "organization", None)


class OrganizationScopedViewSet(viewsets.ModelViewSet):
    """Base viewset that scopes querysets to the active organization."""

    def get_queryset(self):
        org = _get_org(self.request)
        qs = super().get_queryset()
        if org:
            return qs.filter(organization=org)
        return qs.none()

    def perform_create(self, serializer):
        org = _get_org(self.request)
        serializer.save(organization=org)


class CylinderTypeViewSet(OrganizationScopedViewSet):
    serializer_class = CylinderTypeSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = CylinderType.objects.all()


class CylinderSKUViewSet(OrganizationScopedViewSet):
    serializer_class = CylinderSKUSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = CylinderSKU.objects.select_related("cylinder_type")


class DealerViewSet(OrganizationScopedViewSet):
    serializer_class = DealerSerializer
    permission_classes = [SalesPermission]
    queryset = Dealer.objects.all()


class LpgProductViewSet(OrganizationScopedViewSet):
    serializer_class = LpgProductSerializer
    permission_classes = [SalesPermission]
    queryset = LpgProduct.objects.all()


class TransportProviderViewSet(OrganizationScopedViewSet):
    serializer_class = TransportProviderSerializer
    permission_classes = [LogisticsPermission]
    queryset = TransportProvider.objects.all()


class VehicleViewSet(OrganizationScopedViewSet):
    serializer_class = VehicleSerializer
    permission_classes = [LogisticsPermission]
    queryset = Vehicle.objects.select_related("provider")


class ConversionRuleViewSet(OrganizationScopedViewSet):
    serializer_class = ConversionRuleSerializer
    permission_classes = [NocPermission]
    queryset = ConversionRule.objects.select_related("cylinder_type")


class InventoryMovementViewSet(OrganizationScopedViewSet):
    serializer_class = InventoryMovementSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = InventoryMovement.objects.select_related("cylinder_sku")

    http_method_names = ["get", "head", "options"]


class NocPurchaseViewSet(OrganizationScopedViewSet):
    serializer_class = NocPurchaseSerializer
    permission_classes = [NocPermission]
    queryset = NocPurchase.objects.select_related("posted_journal")

    @action(detail=True, methods=["post"])
    def post_purchase(self, request, pk=None):
        purchase = self.get_object()
        post_noc_purchase(purchase, user=request.user)
        serializer = self.get_serializer(purchase)
        return Response(serializer.data)


class SalesInvoiceViewSet(OrganizationScopedViewSet):
    serializer_class = SalesInvoiceSerializer
    permission_classes = [SalesPermission]
    queryset = SalesInvoice.objects.select_related("dealer", "posted_journal").prefetch_related("lines")

    @action(detail=True, methods=["post"])
    def post_invoice(self, request, pk=None):
        invoice = self.get_object()
        post_sales_invoice(invoice, user=request.user)
        serializer = self.get_serializer(invoice)
        return Response(serializer.data)


class LogisticsTripViewSet(OrganizationScopedViewSet):
    serializer_class = LogisticsTripSerializer
    permission_classes = [LogisticsPermission]
    queryset = LogisticsTrip.objects.select_related("provider", "vehicle", "cylinder_sku")

    @action(detail=True, methods=["post"])
    def post_trip(self, request, pk=None):
        trip = self.get_object()
        post_logistics_trip(trip, user=request.user)
        serializer = self.get_serializer(trip)
        return Response(serializer.data)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def dashboard_summary_view(request):
    org = _get_org(request)
    start = parse_date(request.GET.get("from") or "") or date.today().replace(day=1)
    end = parse_date(request.GET.get("to") or "") or date.today()
    data = dashboard_summary(org, start, end)
    return Response(data)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def revenue_expense_trend_view(request):
    org = _get_org(request)
    trend = revenue_expense_trend(org, months=6)
    return Response(trend)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def profit_and_loss_view(request):
    org = _get_org(request)
    start = parse_date(request.GET.get("from")) or date.today().replace(day=1)
    end = parse_date(request.GET.get("to")) or date.today()
    data = profit_and_loss(org, start, end)
    return Response(data)


# ---------------------------------------------------------------------------
# SPA (HTMX) views
# ---------------------------------------------------------------------------


class LpgSpaView(TemplateView):
    template_name = "lpg_vertical/spa.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["organization"] = _get_org(self.request)
        return ctx

    def get_template_names(self):
        # Always render the full SPA page to keep consistent chrome and spacing.
        return [self.template_name]


def _handle_form(request, form_class, form_name=None):
    org = _get_org(request)
    is_target_form = form_name is None or request.POST.get("form_name") == form_name
    data = request.POST if (request.method == "POST" and is_target_form) else None
    form = form_class(organization=org, data=data)
    if request.method == "POST" and is_target_form and form.is_valid():
        form.save()
        messages.success(request, "Saved successfully.")
        form = form_class(organization=org)
    return form


def spa_masters(request):
    org = _get_org(request)
    context = {
        "cylinder_types": CylinderType.objects.filter(organization=org).order_by("name"),
        "cylinder_skus": CylinderSKU.objects.filter(organization=org).select_related("cylinder_type").order_by("code"),
        "dealers": Dealer.objects.filter(organization=org).order_by("company_code"),
        "providers": TransportProvider.objects.filter(organization=org).order_by("name"),
        "vehicles": Vehicle.objects.filter(organization=org).select_related("provider").order_by("number"),
        "conversion_rules": ConversionRule.objects.filter(organization=org).select_related("cylinder_type"),
        "products": LpgProduct.objects.filter(organization=org).order_by("code"),
        "cylinder_type_form": _handle_form(request, lpg_forms.CylinderTypeForm, "cylinder_type"),
        "cylinder_sku_form": _handle_form(request, lpg_forms.CylinderSKUForm, "cylinder_sku"),
        "dealer_form": _handle_form(request, lpg_forms.DealerForm, "dealer"),
        "provider_form": _handle_form(request, lpg_forms.TransportProviderForm, "provider"),
        "vehicle_form": _handle_form(request, lpg_forms.VehicleForm, "vehicle"),
        "conversion_form": _handle_form(request, lpg_forms.ConversionRuleForm, "conversion"),
        "product_form": _handle_form(request, lpg_forms.LpgProductForm, "product"),
    }
    return render(request, "lpg_vertical/partials/masters.html", context)


def spa_noc(request):
    org = _get_org(request)
    form = _handle_form(request, lpg_forms.NocPurchaseForm, "noc")
    purchases = NocPurchase.objects.filter(organization=org).order_by("-date", "-id")[:20]
    return render(
        request,
        "lpg_vertical/partials/noc.html",
        {"form": form, "purchases": purchases},
    )


def spa_sales(request):
    org = _get_org(request)
    form = _handle_form(request, lpg_forms.SalesInvoiceForm, "sales")
    invoices = SalesInvoice.objects.filter(organization=org).select_related("dealer").order_by("-date", "-id")[:20]
    return render(request, "lpg_vertical/partials/sales.html", {"form": form, "invoices": invoices})


def spa_logistics(request):
    org = _get_org(request)
    form = _handle_form(request, lpg_forms.LogisticsTripForm, "logistics")
    trips = (
        LogisticsTrip.objects.filter(organization=org)
        .select_related("provider", "vehicle", "cylinder_sku")
        .order_by("-date", "-id")[:20]
    )
    return render(request, "lpg_vertical/partials/logistics.html", {"form": form, "trips": trips})


def spa_dashboard(request):
    org = _get_org(request)
    today = date.today()
    summary = dashboard_summary(org, today.replace(day=1), today)
    trend = revenue_expense_trend(org, months=6)
    return render(request, "lpg_vertical/partials/dashboard.html", {"summary": summary, "trend": trend})
