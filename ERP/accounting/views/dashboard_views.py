from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from accounting.services.dashboard_service import DashboardService
from accounting.services.tax_liability_service import TaxLiabilityService


class DashboardView(View):
    template_name = "accounting/dashboard.html"

    def get(self, request):
        organization = request.user.get_active_organization()
        if not organization:
            return render(request, self.template_name, {"error": "Select an organization before viewing the dashboard."})
        service = DashboardService(organization)
        context = {
            "metrics": service.get_dashboard_metrics(),
            "export_url": reverse("accounting:dashboard_export"),
        }
        return render(request, self.template_name, context)


class ComplianceView(View):
    template_name = "accounting/compliance.html"

    def get(self, request):
        organization = request.user.get_active_organization()
        context = {}
        if organization:
            liabilities = TaxLiabilityService(organization).aggregate(timezone.now().replace(day=1))
            context.update(
                {
                    "organization": organization,
                    "liabilities": liabilities,
                    "export_url": reverse("accounting:export_compliance"),
                }
            )
        else:
            context["error"] = "Select an organization before viewing compliance data."
        return render(request, self.template_name, context)
