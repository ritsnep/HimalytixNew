from decimal import Decimal

from django.http import request
from django.shortcuts import redirect, render
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.views.generic import TemplateView

from usermanagement.authentication import CustomAuthenticationBackend
from usermanagement.models import LoginLog

User = get_user_model()
# class PagesView(LoginRequiredMixin, TemplateView):
class PagesView(TemplateView):
    pass

BETA_PRODUCTS = [
    {
        "sku": "CRD-TRD-5000",
        "name": "ProRunner Treadmill 5000",
        "stock": 12,
        "unit_cost": Decimal("1500"),
        "image": "images/product/img-1.png",
    },
    {
        "sku": "STR-DMB-SET",
        "name": "Hex Dumbbell Set (5-50lbs)",
        "stock": 8,
        "unit_cost": Decimal("450"),
        "image": "images/product/img-2.png",
    },
    {
        "sku": "ACG-MAT-001",
        "name": "Yoga Mat Premium",
        "stock": 150,
        "unit_cost": Decimal("15"),
        "image": "images/product/img-3.png",
    },
    {
        "sku": "STR-BAR-20",
        "name": "Olympic Barbell 20kg",
        "stock": 4,
        "unit_cost": Decimal("120"),
        "image": "images/product/img-4.png",
    },
    {
        "sku": "STR-KB-16",
        "name": "Kettlebell 16kg",
        "stock": 45,
        "unit_cost": Decimal("25"),
        "image": "images/product/img-5.png",
    },
    {
        "sku": "CRD-ROW-100",
        "name": "Rowing Machine Elite",
        "stock": 2,
        "unit_cost": Decimal("600"),
        "image": "images/product/img-6.png",
    },
]

BETA_VENDORS = [
    "Global Fitness Supply",
    "Peak Performance Suppliers",
    "Powerhouse Distribution",
]

BETA_TAX_RATE = Decimal("0.13")


def _beta_find_product(sku):
    return next((p for p in BETA_PRODUCTS if p["sku"] == sku), None)


def _beta_filter_products(search_query: str):
    if not search_query:
        return BETA_PRODUCTS
    query = search_query.lower()
    return [
        product
        for product in BETA_PRODUCTS
        if query in product["name"].lower() or query in product["sku"].lower()
    ]


def _beta_default_lines():
    return {
        "ACG-MAT-001": {"quantity": 3, "unit_cost": "15"},
        "STR-BAR-20": {"quantity": 1, "unit_cost": "120"},
        "CRD-ROW-100": {"quantity": 1, "unit_cost": "600"},
        "STR-KB-16": {"quantity": 1, "unit_cost": "25"},
        "STR-DMB-SET": {"quantity": 4, "unit_cost": "450"},
    }


def _beta_get_order(request):
    order = request.session.get(
        "beta_purchase_order",
        {
            "vendor": BETA_VENDORS[0],
            "lines": _beta_default_lines(),
            "payment_status": "Payment Due",
        },
    )
    request.session["beta_purchase_order"] = order
    return order


def _beta_mutate_line(order, sku, action):
    product = _beta_find_product(sku)
    if not product:
        return

    lines = order.setdefault("lines", {})
    line = lines.get(sku, {"quantity": 0, "unit_cost": str(product["unit_cost"])})
    quantity = int(line.get("quantity", 0) or 0)

    if action == "remove":
        lines.pop(sku, None)
        return

    if action == "decrement":
        quantity = max(0, quantity - 1)
    else:  # default add/increment
        quantity += 1

    if quantity <= 0:
        lines.pop(sku, None)
    else:
        line["quantity"] = quantity
        line["unit_cost"] = str(line.get("unit_cost") or product["unit_cost"])
        lines[sku] = line


def _beta_build_order_context(order):
    lines = []
    subtotal = Decimal("0.00")

    for sku, payload in order.get("lines", {}).items():
        product = _beta_find_product(sku)
        if not product:
            continue

        qty = int(payload.get("quantity", 0) or 0)
        if qty <= 0:
            continue

        unit_cost = Decimal(str(payload.get("unit_cost", product["unit_cost"])))
        line_total = (unit_cost * qty).quantize(Decimal("0.01"))
        subtotal += line_total

        lines.append(
            {
                "sku": sku,
                "name": product["name"],
                "quantity": qty,
                "unit_cost": unit_cost,
                "line_total": line_total,
            }
        )

    sales_tax = (subtotal * BETA_TAX_RATE).quantize(Decimal("0.01"))
    grand_total = (subtotal + sales_tax).quantize(Decimal("0.01"))

    return {
        "order_lines": lines,
        "subtotal": subtotal.quantize(Decimal("0.01")),
        "sales_tax": sales_tax,
        "grand_total": grand_total,
        "vendor": order.get("vendor", BETA_VENDORS[0]),
        "vendors": BETA_VENDORS,
        "payment_status": order.get("payment_status", "Payment Due"),
        "tax_rate": int(BETA_TAX_RATE * 100),
    }


#  Authentication
pages_authentication_login_view = PagesView.as_view(
    template_name="pages/authentication/auth-login.html"
)

def LoginView(request):
    # credentials = {
    #     'username': request.POST.get('username'),
    #     'password': request.POST.get('password')
    # }
    
    # user = CustomAuthenticationBackend().authenticate(request, **credentials)
    # login_log = LoginLog.objects.filter(user=request.user).latest('login_datetime')

    return render(request, "pages/authentication/auth-login.html"
                #   , {'login_log': login_log}
                  )

pages_authentication_register_view = PagesView.as_view(
    template_name="pages/authentication/auth-register.html"
)
pages_authentication_recoverpw_view = PagesView.as_view(
    template_name="pages/authentication/auth-recoverpw.html"
)
pages_authentication_lockscreen_view = PagesView.as_view(
    template_name="pages/authentication/auth-lock-screen.html"
)
pages_authentication_logout_view = PagesView.as_view(
    template_name="pages/authentication/auth-logout.html"
)
pages_authentication_confirm_mail_view = PagesView.as_view(
    template_name="pages/authentication/auth-confirm-mail.html"
)
pages_authentication_email_verification_view = PagesView.as_view(
    template_name="pages/authentication/auth-email-verification.html"
)
pages_authentication_two_step_verification_view = PagesView.as_view(
    template_name="pages/authentication/auth-two-step-verification.html"
)
#  Pages
pages_starter_page_view = PagesView.as_view(template_name="pages/pages-starter.html")
pages_maintenance_view = PagesView.as_view(template_name="pages/pages-maintenance.html")
pages_comingsoon_view = PagesView.as_view(template_name="pages/pages-comingsoon.html")
pages_timeline_view = PagesView.as_view(template_name="pages/pages-timeline.html")
pages_faqs_view = PagesView.as_view(template_name="pages/pages-faqs.html")
pages_pricing_view = PagesView.as_view(template_name="pages/pages-pricing.html")
pages_error_404_view = PagesView.as_view(template_name="pages/pages-404.html")
pages_error_500_view = PagesView.as_view(template_name="pages/pages-500.html")


# Horizontal
pages_horizontal_layout_view = PagesView.as_view(
    template_name="pages/horizontal/layouts-horizontal.html"
)


class BetaPurchaseOrderView(View):
    template_name = "pages/beta/purchase_order_htmx.html"

    def get(self, request):
        search_query = request.GET.get("search", "").strip()
        order = _beta_get_order(request)
        context = {
            "page_title": "Purchase Flow (HTMX)",
            "search_query": search_query,
            "products": _beta_filter_products(search_query),
            **_beta_build_order_context(order),
        }

        if request.headers.get("HX-Request") and request.GET.get("fragment") == "grid":
            return render(request, "pages/beta/_product_grid.html", context)

        return render(request, self.template_name, context)


class BetaPurchaseCartView(View):
    template_name = "pages/beta/_order_summary.html"

    def post(self, request):
        order = _beta_get_order(request)
        sku = request.POST.get("sku")
        action = request.POST.get("action", "add")
        vendor = request.POST.get("vendor")

        if vendor:
            order["vendor"] = vendor
        if sku:
            _beta_mutate_line(order, sku, action)

        request.session["beta_purchase_order"] = order
        request.session.modified = True

        context = {
            "page_title": "Purchase Flow (HTMX)",
            **_beta_build_order_context(order),
        }
        return render(request, self.template_name, context)


class BetaModelFormView(TemplateView):
    template_name = "pages/beta/model_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Beta Model Form",
                "form_title": "Create Beta Model",
                "form_subtitle": "Dason form shell for new beta entities.",
                "breadcrumbs": [("Beta", None), ("Model Form", None)],
                "model_states": ["Draft", "Active", "On Hold"],
                "owners": ["Finance", "Operations", "Inventory", "Projects"],
                "dimensions": ["Cost Center", "Department", "Project", "Warehouse"],
            }
        )
        return context


class BetaModelListView(TemplateView):
    template_name = "pages/beta/model_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        beta_models = [
            {
                "code": "BETA-001",
                "name": "Studio Build",
                "category": "Operations",
                "owner": "Avery Ross",
                "status": "Active",
                "updated": "2025-12-10",
            },
            {
                "code": "BETA-002",
                "name": "Retail Fixtures",
                "category": "Inventory",
                "owner": "Priya Desai",
                "status": "Draft",
                "updated": "2025-12-09",
            },
            {
                "code": "BETA-003",
                "name": "Q1 Lease Fit-out",
                "category": "Projects",
                "owner": "Luis Gomez",
                "status": "On Hold",
                "updated": "2025-12-07",
            },
            {
                "code": "BETA-004",
                "name": "Regional Launch Prep",
                "category": "Finance",
                "owner": "Hannah Lee",
                "status": "Active",
                "updated": "2025-12-05",
            },
        ]
        active_count = len([m for m in beta_models if m["status"] == "Active"])

        context.update(
            {
                "page_title": "Beta Model List",
                "page_subtitle": "Dason list template wired for quick filters.",
                "breadcrumbs": [("Beta", None), ("Model List", None)],
                "beta_models": beta_models,
                "model_metrics": {
                    "total": len(beta_models),
                    "active": active_count,
                    "draft": len([m for m in beta_models if m["status"] == "Draft"]),
                },
            }
        )
        return context
