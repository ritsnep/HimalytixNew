from django.contrib import messages
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView, TemplateView
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
import csv
from io import StringIO

from accounting.mixins import PermissionRequiredMixin, UserOrganizationMixin
from accounting.views.base_views import BaseListView
from accounting.services.report_export_service import ReportExportService
from accounting.models import IntegrationEvent
from . import forms
from .models import (
    Department,
    Position,
    Employee,
    PayrollCycle,
    PayrollEntry,
    LeaveRequest,
    AttendanceRecord,
    BenefitEnrollment,
    FixedAssetCategory,
    FixedAsset,
    AssetDepreciationSchedule,
    BillOfMaterial,
    BillOfMaterialItem,
    WorkOrder,
    WorkOrderMaterial,
    WorkCenter,
    Routing,
    WorkOrderOperation,
    CRMLead,
    Opportunity,
    Campaign,
    Budget,
    BudgetLine,
    IntegrationEndpoint,
    IntegrationCredential,
    WebhookSubscription,
    POSDevice,
    LocaleConfig,
    TaxRegime,
    PayComponent,
    PayrollRun,
    PayrollRunLine,
)
from .services import FixedAssetService, PayrollService
from .services import BudgetVarianceService, MRPService
from .services import PayrollService


class EnterpriseListView(PermissionRequiredMixin, BaseListView):
    """Org-scoped list view with RBAC and simple column definition."""

    template_name = "enterprise/list.html"
    list_display = ()
    create_url_name = None
    update_url_name = None

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_display"] = self.list_display
        ctx["create_url"] = reverse(self.create_url_name) if self.create_url_name else None
        ctx["update_url_name"] = self.update_url_name
        ctx["page_title"] = self.model._meta.verbose_name_plural.title()
        return ctx


class EnterpriseFormView(PermissionRequiredMixin, UserOrganizationMixin):
    """Mixin for create/update views to set org, permissions, and breadcrumbs."""

    template_name = "enterprise/form.html"
    form_title = ""
    success_url_name = ""
    back_url_name = ""

    def get_success_url(self):
        return reverse(self.success_url_name)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form_title"] = self.form_title
        ctx["back_url"] = reverse(self.back_url_name)
        ctx["page_title"] = self.form_title
        return ctx

    def form_valid(self, form):
        form.organization = self.get_organization()
        messages.success(self.request, f"{self.model._meta.verbose_name.title()} saved.")
        return super().form_valid(form)


class EnterpriseCreateView(EnterpriseFormView, CreateView):
    pass


class EnterpriseUpdateView(EnterpriseFormView, UpdateView):
    pass


# -----------------------
# HR / Payroll
# -----------------------
class DepartmentListView(EnterpriseListView):
    model = Department
    list_display = ("name", "code")
    create_url_name = "enterprise:department_create"
    update_url_name = "enterprise:department_update"
    permission_required = ("enterprise", "department", "view")


class DepartmentCreateView(EnterpriseCreateView):
    model = Department
    form_class = forms.DepartmentForm
    form_title = "Create Department"
    success_url_name = "enterprise:department_list"
    back_url_name = "enterprise:department_list"
    permission_required = ("enterprise", "department", "add")


class DepartmentUpdateView(EnterpriseUpdateView):
    model = Department
    form_class = forms.DepartmentForm
    form_title = "Edit Department"
    success_url_name = "enterprise:department_list"
    back_url_name = "enterprise:department_list"
    permission_required = ("enterprise", "department", "change")


class PositionListView(EnterpriseListView):
    model = Position
    list_display = ("title", "department", "grade")
    create_url_name = "enterprise:position_create"
    update_url_name = "enterprise:position_update"
    permission_required = ("enterprise", "position", "view")


class PositionCreateView(EnterpriseCreateView):
    model = Position
    form_class = forms.PositionForm
    form_title = "Create Position"
    success_url_name = "enterprise:position_list"
    back_url_name = "enterprise:position_list"
    permission_required = ("enterprise", "position", "add")


class PositionUpdateView(EnterpriseUpdateView):
    model = Position
    form_class = forms.PositionForm
    form_title = "Edit Position"
    success_url_name = "enterprise:position_list"
    back_url_name = "enterprise:position_list"
    permission_required = ("enterprise", "position", "change")


class EmployeeListView(EnterpriseListView):
    model = Employee
    list_display = ("employee_id", "first_name", "last_name", "department", "position", "status")
    create_url_name = "enterprise:employee_create"
    update_url_name = "enterprise:employee_update"
    permission_required = ("enterprise", "employee", "view")


class EmployeeCreateView(EnterpriseCreateView):
    model = Employee
    form_class = forms.EmployeeForm
    form_title = "Create Employee"
    success_url_name = "enterprise:employee_list"
    back_url_name = "enterprise:employee_list"
    permission_required = ("enterprise", "employee", "add")


class EmployeeUpdateView(EnterpriseUpdateView):
    model = Employee
    form_class = forms.EmployeeForm
    form_title = "Edit Employee"
    success_url_name = "enterprise:employee_list"
    back_url_name = "enterprise:employee_list"
    permission_required = ("enterprise", "employee", "change")


class PayrollCycleListView(EnterpriseListView):
    model = PayrollCycle
    list_display = ("name", "period_start", "period_end", "status")
    create_url_name = "enterprise:payroll_cycle_create"
    update_url_name = "enterprise:payroll_cycle_update"
    permission_required = ("enterprise", "payrollcycle", "view")


class PayrollCycleCreateView(EnterpriseCreateView):
    model = PayrollCycle
    form_class = forms.PayrollCycleForm
    form_title = "Create Payroll Cycle"
    success_url_name = "enterprise:payroll_cycle_list"
    back_url_name = "enterprise:payroll_cycle_list"
    permission_required = ("enterprise", "payrollcycle", "add")


class PayrollCycleUpdateView(EnterpriseUpdateView):
    model = PayrollCycle
    form_class = forms.PayrollCycleForm
    form_title = "Edit Payroll Cycle"
    success_url_name = "enterprise:payroll_cycle_list"
    back_url_name = "enterprise:payroll_cycle_list"
    permission_required = ("enterprise", "payrollcycle", "change")


class PayrollEntryListView(EnterpriseListView):
    model = PayrollEntry
    list_display = ("payroll_cycle", "employee", "gross_pay", "net_pay", "currency")
    create_url_name = "enterprise:payroll_entry_create"
    update_url_name = "enterprise:payroll_entry_update"
    permission_required = ("enterprise", "payrollentry", "view")


class PayrollEntryCreateView(EnterpriseCreateView):
    model = PayrollEntry
    form_class = forms.PayrollEntryForm
    form_title = "Create Payroll Entry"
    success_url_name = "enterprise:payroll_entry_list"
    back_url_name = "enterprise:payroll_entry_list"
    permission_required = ("enterprise", "payrollentry", "add")


class PayrollEntryUpdateView(EnterpriseUpdateView):
    model = PayrollEntry
    form_class = forms.PayrollEntryForm
    form_title = "Edit Payroll Entry"
    success_url_name = "enterprise:payroll_entry_list"
    back_url_name = "enterprise:payroll_entry_list"
    permission_required = ("enterprise", "payrollentry", "change")


class PayComponentListView(EnterpriseListView):
    model = PayComponent
    list_display = ("code", "name", "component_type", "amount_type", "amount_value", "is_active")
    create_url_name = "enterprise:paycomponent_create"
    update_url_name = "enterprise:paycomponent_update"
    permission_required = ("enterprise", "paycomponent", "view")


class PayComponentCreateView(EnterpriseCreateView):
    model = PayComponent
    form_class = forms.PayComponentForm
    form_title = "Create Pay Component"
    success_url_name = "enterprise:paycomponent_list"
    back_url_name = "enterprise:paycomponent_list"
    permission_required = ("enterprise", "paycomponent", "add")


class PayComponentUpdateView(EnterpriseUpdateView):
    model = PayComponent
    form_class = forms.PayComponentForm
    form_title = "Edit Pay Component"
    success_url_name = "enterprise:paycomponent_list"
    back_url_name = "enterprise:paycomponent_list"
    permission_required = ("enterprise", "paycomponent", "change")


class PayrollRunListView(EnterpriseListView):
    model = PayrollRun
    list_display = ("payroll_cycle", "period_start", "period_end", "status")
    create_url_name = "enterprise:payroll_run_create"
    update_url_name = "enterprise:payroll_run_update"
    permission_required = ("enterprise", "payrollrun", "view")


class PayrollRunCreateView(EnterpriseCreateView):
    model = PayrollRun
    form_class = forms.PayrollRunForm
    form_title = "Create Payroll Run"
    success_url_name = "enterprise:payroll_run_list"
    back_url_name = "enterprise:payroll_run_list"
    permission_required = ("enterprise", "payrollrun", "add")


class PayrollRunUpdateView(EnterpriseUpdateView):
    model = PayrollRun
    form_class = forms.PayrollRunForm
    form_title = "Edit Payroll Run"
    success_url_name = "enterprise:payroll_run_list"
    back_url_name = "enterprise:payroll_run_list"
    permission_required = ("enterprise", "payrollrun", "change")


class PayrollRunLineListView(EnterpriseListView):
    model = PayrollRunLine
    list_display = ("payroll_run", "employee", "component", "amount")
    create_url_name = "enterprise:payroll_run_line_create"
    update_url_name = "enterprise:payroll_run_line_update"
    permission_required = ("enterprise", "payrollrunline", "view")


class PayrollRunLineCreateView(EnterpriseCreateView):
    model = PayrollRunLine
    form_class = forms.PayrollRunLineForm
    form_title = "Add Payroll Line"
    success_url_name = "enterprise:payroll_run_line_list"
    back_url_name = "enterprise:payroll_run_line_list"
    permission_required = ("enterprise", "payrollrunline", "add")


class PayrollRunLineUpdateView(EnterpriseUpdateView):
    model = PayrollRunLine
    form_class = forms.PayrollRunLineForm
    form_title = "Edit Payroll Line"
    success_url_name = "enterprise:payroll_run_line_list"
    back_url_name = "enterprise:payroll_run_line_list"
    permission_required = ("enterprise", "payrollrunline", "change")


class LeaveRequestListView(EnterpriseListView):
    model = LeaveRequest
    list_display = ("employee", "leave_type", "start_date", "end_date", "status")
    create_url_name = "enterprise:leave_request_create"
    update_url_name = "enterprise:leave_request_update"
    permission_required = ("enterprise", "leaverequest", "view")


class LeaveRequestCreateView(EnterpriseCreateView):
    model = LeaveRequest
    form_class = forms.LeaveRequestForm
    form_title = "Create Leave Request"
    success_url_name = "enterprise:leave_request_list"
    back_url_name = "enterprise:leave_request_list"
    permission_required = ("enterprise", "leaverequest", "add")


class LeaveRequestUpdateView(EnterpriseUpdateView):
    model = LeaveRequest
    form_class = forms.LeaveRequestForm
    form_title = "Edit Leave Request"
    success_url_name = "enterprise:leave_request_list"
    back_url_name = "enterprise:leave_request_list"
    permission_required = ("enterprise", "leaverequest", "change")


class AttendanceRecordListView(EnterpriseListView):
    model = AttendanceRecord
    list_display = ("employee", "work_date", "hours_worked", "status")
    create_url_name = "enterprise:attendance_record_create"
    update_url_name = "enterprise:attendance_record_update"
    permission_required = ("enterprise", "attendancerecord", "view")


class AttendanceRecordCreateView(EnterpriseCreateView):
    model = AttendanceRecord
    form_class = forms.AttendanceRecordForm
    form_title = "Create Attendance Record"
    success_url_name = "enterprise:attendance_record_list"
    back_url_name = "enterprise:attendance_record_list"
    permission_required = ("enterprise", "attendancerecord", "add")


class AttendanceRecordUpdateView(EnterpriseUpdateView):
    model = AttendanceRecord
    form_class = forms.AttendanceRecordForm
    form_title = "Edit Attendance Record"
    success_url_name = "enterprise:attendance_record_list"
    back_url_name = "enterprise:attendance_record_list"
    permission_required = ("enterprise", "attendancerecord", "change")


class BenefitEnrollmentListView(EnterpriseListView):
    model = BenefitEnrollment
    list_display = ("employee", "benefit_name", "contribution", "employer_contribution")
    create_url_name = "enterprise:benefit_enrollment_create"
    update_url_name = "enterprise:benefit_enrollment_update"
    permission_required = ("enterprise", "benefitenrollment", "view")


class BenefitEnrollmentCreateView(EnterpriseCreateView):
    model = BenefitEnrollment
    form_class = forms.BenefitEnrollmentForm
    form_title = "Create Benefit Enrollment"
    success_url_name = "enterprise:benefit_enrollment_list"
    back_url_name = "enterprise:benefit_enrollment_list"
    permission_required = ("enterprise", "benefitenrollment", "add")


class BenefitEnrollmentUpdateView(EnterpriseUpdateView):
    model = BenefitEnrollment
    form_class = forms.BenefitEnrollmentForm
    form_title = "Edit Benefit Enrollment"
    success_url_name = "enterprise:benefit_enrollment_list"
    back_url_name = "enterprise:benefit_enrollment_list"
    permission_required = ("enterprise", "benefitenrollment", "change")


# -----------------------
# Fixed Assets
# -----------------------
class FixedAssetCategoryListView(EnterpriseListView):
    model = FixedAssetCategory
    list_display = ("name", "depreciation_method", "useful_life_months", "salvage_value_rate")
    create_url_name = "enterprise:fixedasset_category_create"
    update_url_name = "enterprise:fixedasset_category_update"
    permission_required = ("enterprise", "fixedassetcategory", "view")


class FixedAssetCategoryCreateView(EnterpriseCreateView):
    model = FixedAssetCategory
    form_class = forms.FixedAssetCategoryForm
    form_title = "Create Fixed Asset Category"
    success_url_name = "enterprise:fixedasset_category_list"
    back_url_name = "enterprise:fixedasset_category_list"
    permission_required = ("enterprise", "fixedassetcategory", "add")


class FixedAssetCategoryUpdateView(EnterpriseUpdateView):
    model = FixedAssetCategory
    form_class = forms.FixedAssetCategoryForm
    form_title = "Edit Fixed Asset Category"
    success_url_name = "enterprise:fixedasset_category_list"
    back_url_name = "enterprise:fixedasset_category_list"
    permission_required = ("enterprise", "fixedassetcategory", "change")


class FixedAssetListView(EnterpriseListView):
    model = FixedAsset
    list_display = ("asset_code", "name", "category", "acquisition_date", "location")
    create_url_name = "enterprise:fixedasset_create"
    update_url_name = "enterprise:fixedasset_update"
    permission_required = ("enterprise", "fixedasset", "view")


class FixedAssetCreateView(EnterpriseCreateView):
    model = FixedAsset
    form_class = forms.FixedAssetForm
    form_title = "Create Fixed Asset"
    success_url_name = "enterprise:fixedasset_list"
    back_url_name = "enterprise:fixedasset_list"
    permission_required = ("enterprise", "fixedasset", "add")


class FixedAssetUpdateView(EnterpriseUpdateView):
    model = FixedAsset
    form_class = forms.FixedAssetForm
    form_title = "Edit Fixed Asset"
    success_url_name = "enterprise:fixedasset_list"
    back_url_name = "enterprise:fixedasset_list"
    permission_required = ("enterprise", "fixedasset", "change")


class AssetDepreciationScheduleListView(EnterpriseListView):
    model = AssetDepreciationSchedule
    list_display = ("asset", "period_start", "period_end", "depreciation_amount", "posted_journal")
    create_url_name = "enterprise:depreciation_schedule_create"
    update_url_name = "enterprise:depreciation_schedule_update"
    permission_required = ("enterprise", "assetdepreciationschedule", "view")


class AssetDepreciationScheduleCreateView(EnterpriseCreateView):
    model = AssetDepreciationSchedule
    form_class = forms.AssetDepreciationScheduleForm
    form_title = "Create Depreciation Schedule"
    success_url_name = "enterprise:depreciation_schedule_list"
    back_url_name = "enterprise:depreciation_schedule_list"
    permission_required = ("enterprise", "assetdepreciationschedule", "add")


class AssetDepreciationScheduleUpdateView(EnterpriseUpdateView):
    model = AssetDepreciationSchedule
    form_class = forms.AssetDepreciationScheduleForm
    form_title = "Edit Depreciation Schedule"
    success_url_name = "enterprise:depreciation_schedule_list"
    back_url_name = "enterprise:depreciation_schedule_list"
    permission_required = ("enterprise", "assetdepreciationschedule", "change")


# -----------------------
# Manufacturing
# -----------------------
class BillOfMaterialListView(EnterpriseListView):
    model = BillOfMaterial
    list_display = ("name", "product_name", "revision")
    create_url_name = "enterprise:bom_create"
    update_url_name = "enterprise:bom_update"
    permission_required = ("enterprise", "billofmaterial", "view")


class BillOfMaterialCreateView(EnterpriseCreateView):
    model = BillOfMaterial
    form_class = forms.BillOfMaterialForm
    form_title = "Create Bill of Material"
    success_url_name = "enterprise:bom_list"
    back_url_name = "enterprise:bom_list"
    permission_required = ("enterprise", "billofmaterial", "add")


class BillOfMaterialUpdateView(EnterpriseUpdateView):
    model = BillOfMaterial
    form_class = forms.BillOfMaterialForm
    form_title = "Edit Bill of Material"
    success_url_name = "enterprise:bom_list"
    back_url_name = "enterprise:bom_list"
    permission_required = ("enterprise", "billofmaterial", "change")


class BillOfMaterialItemListView(EnterpriseListView):
    model = BillOfMaterialItem
    list_display = ("bill_of_material", "component_name", "quantity", "uom")
    create_url_name = "enterprise:bom_item_create"
    update_url_name = "enterprise:bom_item_update"
    permission_required = ("enterprise", "billofmaterialitem", "view")


class BillOfMaterialItemCreateView(EnterpriseCreateView):
    model = BillOfMaterialItem
    form_class = forms.BillOfMaterialItemForm
    form_title = "Add BOM Item"
    success_url_name = "enterprise:bom_item_list"
    back_url_name = "enterprise:bom_item_list"
    permission_required = ("enterprise", "billofmaterialitem", "add")


class BillOfMaterialItemUpdateView(EnterpriseUpdateView):
    model = BillOfMaterialItem
    form_class = forms.BillOfMaterialItemForm
    form_title = "Edit BOM Item"
    success_url_name = "enterprise:bom_item_list"
    back_url_name = "enterprise:bom_item_list"
    permission_required = ("enterprise", "billofmaterialitem", "change")


class WorkOrderListView(EnterpriseListView):
    model = WorkOrder
    list_display = ("work_order_number", "bill_of_material", "quantity_to_produce", "status", "planned_start")
    create_url_name = "enterprise:workorder_create"
    update_url_name = "enterprise:workorder_update"
    permission_required = ("enterprise", "workorder", "view")


class WorkOrderCreateView(EnterpriseCreateView):
    model = WorkOrder
    form_class = forms.WorkOrderForm
    form_title = "Create Work Order"
    success_url_name = "enterprise:workorder_list"
    back_url_name = "enterprise:workorder_list"
    permission_required = ("enterprise", "workorder", "add")


class WorkOrderUpdateView(EnterpriseUpdateView):
    model = WorkOrder
    form_class = forms.WorkOrderForm
    form_title = "Edit Work Order"
    success_url_name = "enterprise:workorder_list"
    back_url_name = "enterprise:workorder_list"
    permission_required = ("enterprise", "workorder", "change")


class WorkOrderMaterialListView(EnterpriseListView):
    model = WorkOrderMaterial
    list_display = ("work_order", "component_name", "quantity_required", "quantity_issued", "uom")
    create_url_name = "enterprise:womaterial_create"
    update_url_name = "enterprise:womaterial_update"
    permission_required = ("enterprise", "workordermaterial", "view")


class WorkOrderMaterialCreateView(EnterpriseCreateView):
    model = WorkOrderMaterial
    form_class = forms.WorkOrderMaterialForm
    form_title = "Add Work Order Material"
    success_url_name = "enterprise:womaterial_list"
    back_url_name = "enterprise:womaterial_list"
    permission_required = ("enterprise", "workordermaterial", "add")


class WorkOrderMaterialUpdateView(EnterpriseUpdateView):
    model = WorkOrderMaterial
    form_class = forms.WorkOrderMaterialForm
    form_title = "Edit Work Order Material"
    success_url_name = "enterprise:womaterial_list"
    back_url_name = "enterprise:womaterial_list"
    permission_required = ("enterprise", "workordermaterial", "change")


class WorkCenterListView(EnterpriseListView):
    model = WorkCenter
    list_display = ("name", "code", "capacity_per_day", "is_active")
    create_url_name = "enterprise:workcenter_create"
    update_url_name = "enterprise:workcenter_update"
    permission_required = ("enterprise", "workcenter", "view")


class WorkCenterCreateView(EnterpriseCreateView):
    model = WorkCenter
    form_class = forms.WorkCenterForm
    form_title = "Create Work Center"
    success_url_name = "enterprise:workcenter_list"
    back_url_name = "enterprise:workcenter_list"
    permission_required = ("enterprise", "workcenter", "add")


class WorkCenterUpdateView(EnterpriseUpdateView):
    model = WorkCenter
    form_class = forms.WorkCenterForm
    form_title = "Edit Work Center"
    success_url_name = "enterprise:workcenter_list"
    back_url_name = "enterprise:workcenter_list"
    permission_required = ("enterprise", "workcenter", "change")


class RoutingListView(EnterpriseListView):
    model = Routing
    list_display = ("name", "work_center", "standard_duration_hours", "is_active")
    create_url_name = "enterprise:routing_create"
    update_url_name = "enterprise:routing_update"
    permission_required = ("enterprise", "routing", "view")


class RoutingCreateView(EnterpriseCreateView):
    model = Routing
    form_class = forms.RoutingForm
    form_title = "Create Routing"
    success_url_name = "enterprise:routing_list"
    back_url_name = "enterprise:routing_list"
    permission_required = ("enterprise", "routing", "add")


class RoutingUpdateView(EnterpriseUpdateView):
    model = Routing
    form_class = forms.RoutingForm
    form_title = "Edit Routing"
    success_url_name = "enterprise:routing_list"
    back_url_name = "enterprise:routing_list"
    permission_required = ("enterprise", "routing", "change")


class WorkOrderOperationListView(EnterpriseListView):
    model = WorkOrderOperation
    list_display = ("work_order", "routing", "sequence", "planned_start", "planned_end", "status")
    create_url_name = "enterprise:workorder_operation_create"
    update_url_name = "enterprise:workorder_operation_update"
    permission_required = ("enterprise", "workorderoperation", "view")


class WorkOrderOperationCreateView(EnterpriseCreateView):
    model = WorkOrderOperation
    form_class = forms.WorkOrderOperationForm
    form_title = "Create Work Order Operation"
    success_url_name = "enterprise:workorder_operation_list"
    back_url_name = "enterprise:workorder_operation_list"
    permission_required = ("enterprise", "workorderoperation", "add")


class WorkOrderOperationUpdateView(EnterpriseUpdateView):
    model = WorkOrderOperation
    form_class = forms.WorkOrderOperationForm
    form_title = "Edit Work Order Operation"
    success_url_name = "enterprise:workorder_operation_list"
    back_url_name = "enterprise:workorder_operation_list"
    permission_required = ("enterprise", "workorderoperation", "change")


class MRPSuggestionsView(PermissionRequiredMixin, UserOrganizationMixin, TemplateView):
    template_name = "enterprise/mrp_suggestions.html"
    permission_required = ("enterprise", "workorder", "view")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        work_order_id = self.request.GET.get("work_order")
        wo = None
        suggestions = []
        if work_order_id:
            wo = WorkOrder.objects.filter(pk=work_order_id, organization=self.get_organization()).first()
        if wo:
            service = MRPService(self.get_organization())
            suggestions = service.suggest_for_workorder(wo)
        ctx["work_order"] = wo
        ctx["work_orders"] = WorkOrder.objects.filter(organization=self.get_organization())
        ctx["suggestions"] = suggestions
        ctx["page_title"] = "MRP Suggestions"
        return ctx


# -----------------------
# CRM
# -----------------------
class CRMLeadListView(EnterpriseListView):
    model = CRMLead
    list_display = ("name", "source", "status", "probability")
    create_url_name = "enterprise:crmlead_create"
    update_url_name = "enterprise:crmlead_update"
    permission_required = ("enterprise", "crmlead", "view")


class CRMLeadCreateView(EnterpriseCreateView):
    model = CRMLead
    form_class = forms.CRMLeadForm
    form_title = "Create Lead"
    success_url_name = "enterprise:crmlead_list"
    back_url_name = "enterprise:crmlead_list"
    permission_required = ("enterprise", "crmlead", "add")


class CRMLeadUpdateView(EnterpriseUpdateView):
    model = CRMLead
    form_class = forms.CRMLeadForm
    form_title = "Edit Lead"
    success_url_name = "enterprise:crmlead_list"
    back_url_name = "enterprise:crmlead_list"
    permission_required = ("enterprise", "crmlead", "change")


class OpportunityListView(EnterpriseListView):
    model = Opportunity
    list_display = ("name", "lead", "stage", "expected_close", "amount", "probability")
    create_url_name = "enterprise:opportunity_create"
    update_url_name = "enterprise:opportunity_update"
    permission_required = ("enterprise", "opportunity", "view")


class OpportunityCreateView(EnterpriseCreateView):
    model = Opportunity
    form_class = forms.OpportunityForm
    form_title = "Create Opportunity"
    success_url_name = "enterprise:opportunity_list"
    back_url_name = "enterprise:opportunity_list"
    permission_required = ("enterprise", "opportunity", "add")


class OpportunityUpdateView(EnterpriseUpdateView):
    model = Opportunity
    form_class = forms.OpportunityForm
    form_title = "Edit Opportunity"
    success_url_name = "enterprise:opportunity_list"
    back_url_name = "enterprise:opportunity_list"
    permission_required = ("enterprise", "opportunity", "change")


class CampaignListView(EnterpriseListView):
    model = Campaign
    list_display = ("name", "channel", "budget_amount", "start_date", "end_date")
    create_url_name = "enterprise:campaign_create"
    update_url_name = "enterprise:campaign_update"
    permission_required = ("enterprise", "campaign", "view")


class CampaignCreateView(EnterpriseCreateView):
    model = Campaign
    form_class = forms.CampaignForm
    form_title = "Create Campaign"
    success_url_name = "enterprise:campaign_list"
    back_url_name = "enterprise:campaign_list"
    permission_required = ("enterprise", "campaign", "add")


class CampaignUpdateView(EnterpriseUpdateView):
    model = Campaign
    form_class = forms.CampaignForm
    form_title = "Edit Campaign"
    success_url_name = "enterprise:campaign_list"
    back_url_name = "enterprise:campaign_list"
    permission_required = ("enterprise", "campaign", "change")


# -----------------------
# Budgeting
# -----------------------
class BudgetListView(EnterpriseListView):
    model = Budget
    list_display = ("name", "fiscal_year", "status")
    create_url_name = "enterprise:budget_create"
    update_url_name = "enterprise:budget_update"
    permission_required = ("enterprise", "budget", "view")


class BudgetCreateView(EnterpriseCreateView):
    model = Budget
    form_class = forms.BudgetForm
    form_title = "Create Budget"
    success_url_name = "enterprise:budget_list"
    back_url_name = "enterprise:budget_list"
    permission_required = ("enterprise", "budget", "add")


class BudgetUpdateView(EnterpriseUpdateView):
    model = Budget
    form_class = forms.BudgetForm
    form_title = "Edit Budget"
    success_url_name = "enterprise:budget_list"
    back_url_name = "enterprise:budget_list"
    permission_required = ("enterprise", "budget", "change")


class BudgetLineListView(EnterpriseListView):
    model = BudgetLine
    list_display = ("budget", "department", "account_code", "amount")
    create_url_name = "enterprise:budgetline_create"
    update_url_name = "enterprise:budgetline_update"
    permission_required = ("enterprise", "budgetline", "view")


class BudgetLineCreateView(EnterpriseCreateView):
    model = BudgetLine
    form_class = forms.BudgetLineForm
    form_title = "Create Budget Line"
    success_url_name = "enterprise:budgetline_list"
    back_url_name = "enterprise:budgetline_list"
    permission_required = ("enterprise", "budgetline", "add")


class BudgetLineUpdateView(EnterpriseUpdateView):
    model = BudgetLine
    form_class = forms.BudgetLineForm
    form_title = "Edit Budget Line"
    success_url_name = "enterprise:budgetline_list"
    back_url_name = "enterprise:budgetline_list"
    permission_required = ("enterprise", "budgetline", "change")


class BudgetVarianceView(PermissionRequiredMixin, UserOrganizationMixin, TemplateView):
    template_name = "enterprise/budget_variance.html"
    permission_required = ("enterprise", "budget", "view")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        budget_id = self.request.GET.get("budget")
        start = self.request.GET.get("start")
        end = self.request.GET.get("end")
        rows = []
        budget = None
        if budget_id:
            budget = Budget.objects.filter(pk=budget_id, organization=self.get_organization()).first()
        if budget:
            service = BudgetVarianceService(self.get_organization())
            rows = service.variances(budget, start_date=start, end_date=end)
        ctx["budget"] = budget
        ctx["budgets"] = Budget.objects.filter(organization=self.get_organization())
        ctx["rows"] = rows
        ctx["page_title"] = "Budget Variance"
        return ctx


# -----------------------
# Integrations
# -----------------------
class IntegrationEndpointListView(EnterpriseListView):
    model = IntegrationEndpoint
    list_display = ("name", "connector_type", "base_url", "is_active")
    create_url_name = "enterprise:integrationendpoint_create"
    update_url_name = "enterprise:integrationendpoint_update"
    permission_required = ("enterprise", "integrationendpoint", "view")


class IntegrationEndpointCreateView(EnterpriseCreateView):
    model = IntegrationEndpoint
    form_class = forms.IntegrationEndpointForm
    form_title = "Create Integration Endpoint"
    success_url_name = "enterprise:integrationendpoint_list"
    back_url_name = "enterprise:integrationendpoint_list"
    permission_required = ("enterprise", "integrationendpoint", "add")


class IntegrationEndpointUpdateView(EnterpriseUpdateView):
    model = IntegrationEndpoint
    form_class = forms.IntegrationEndpointForm
    form_title = "Edit Integration Endpoint"
    success_url_name = "enterprise:integrationendpoint_list"
    back_url_name = "enterprise:integrationendpoint_list"
    permission_required = ("enterprise", "integrationendpoint", "change")


class POSDeviceListView(EnterpriseListView):
    model = POSDevice
    list_display = ("identifier", "location", "status")
    create_url_name = "enterprise:posdevice_create"
    update_url_name = "enterprise:posdevice_update"
    permission_required = ("enterprise", "posdevice", "view")


class POSDeviceCreateView(EnterpriseCreateView):
    model = POSDevice
    form_class = forms.POSDeviceForm
    form_title = "Create POS Device"
    success_url_name = "enterprise:posdevice_list"
    back_url_name = "enterprise:posdevice_list"
    permission_required = ("enterprise", "posdevice", "add")


class POSDeviceUpdateView(EnterpriseUpdateView):
    model = POSDevice
    form_class = forms.POSDeviceForm
    form_title = "Edit POS Device"
    success_url_name = "enterprise:posdevice_list"
    back_url_name = "enterprise:posdevice_list"
    permission_required = ("enterprise", "posdevice", "change")


# -----------------------
# Localization & Tax
# -----------------------
class LocaleConfigListView(EnterpriseListView):
    model = LocaleConfig
    list_display = ("locale_code", "timezone", "default_currency", "tax_region", "enable_e_invoicing")
    create_url_name = "enterprise:localeconfig_create"
    update_url_name = "enterprise:localeconfig_update"
    permission_required = ("enterprise", "localeconfig", "view")


class LocaleConfigCreateView(EnterpriseCreateView):
    model = LocaleConfig
    form_class = forms.LocaleConfigForm
    form_title = "Create Locale Config"
    success_url_name = "enterprise:localeconfig_list"
    back_url_name = "enterprise:localeconfig_list"
    permission_required = ("enterprise", "localeconfig", "add")


class LocaleConfigUpdateView(EnterpriseUpdateView):
    model = LocaleConfig
    form_class = forms.LocaleConfigForm
    form_title = "Edit Locale Config"
    success_url_name = "enterprise:localeconfig_list"
    back_url_name = "enterprise:localeconfig_list"
    permission_required = ("enterprise", "localeconfig", "change")


class TaxRegimeListView(EnterpriseListView):
    model = TaxRegime
    list_display = ("name", "country", "region", "e_invoice_format", "is_active")
    create_url_name = "enterprise:taxregime_create"
    update_url_name = "enterprise:taxregime_update"
    permission_required = ("enterprise", "taxregime", "view")


class TaxRegimeCreateView(EnterpriseCreateView):
    model = TaxRegime
    form_class = forms.TaxRegimeForm
    form_title = "Create Tax Regime"
    success_url_name = "enterprise:taxregime_list"
    back_url_name = "enterprise:taxregime_list"
    permission_required = ("enterprise", "taxregime", "add")


class TaxRegimeUpdateView(EnterpriseUpdateView):
    model = TaxRegime
    form_class = forms.TaxRegimeForm
    form_title = "Edit Tax Regime"
    success_url_name = "enterprise:taxregime_list"
    back_url_name = "enterprise:taxregime_list"
    permission_required = ("enterprise", "taxregime", "change")


# -----------------------
# Reports
# -----------------------
class DepreciationReportView(PermissionRequiredMixin, UserOrganizationMixin, TemplateView):
    template_name = "enterprise/depreciation_report.html"
    permission_required = ("enterprise", "fixedasset", "view")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        org = self.get_organization()
        assets = FixedAsset.objects.filter(organization=org).select_related("category")
        rows = []
        for asset in assets:
            rows.append(
                {
                    "asset": asset,
                    "category": asset.category,
                    "acquisition_cost": asset.acquisition_cost,
                    "salvage_value": asset.salvage_value,
                    "accumulated": asset.accumulated_depreciation,
                    "book_value": asset.book_value,
                    "status": asset.status,
                }
            )
        ctx["rows"] = rows
        ctx["page_title"] = "Depreciation Report"
        return ctx


# -----------------------
# Payroll exports/actions
# -----------------------
def export_payroll_run(request, pk):
    run = PayrollRun.objects.select_related("organization").get(pk=pk)
    org = run.organization
    if request.user.get_active_organization() != org and not request.user.is_superuser:
        return HttpResponse(status=403)

    service = PayrollService(request.user, org)
    service.generate_entries(run)

    fmt = request.GET.get("format", "csv")
    entries = run.entries.select_related("employee")
    if fmt in ["csv", "xls"]:
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            ["Employee", "Gross Pay", "Deductions", "Net Pay", "Currency", "Payroll Run"]
        )
        for entry in entries:
            writer.writerow(
                [
                    str(entry.employee),
                    entry.gross_pay,
                    entry.deductions,
                    entry.net_pay,
                    entry.currency,
                    run.period_end,
                ]
            )
        content_type = "text/csv" if fmt == "csv" else "application/vnd.ms-excel"
        response = HttpResponse(output.getvalue(), content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="payroll_run_{pk}.{fmt}"'
        return response
    if fmt == "pdf":
        rows = []
        for entry in entries:
            rows.append(
                {
                    "employee": str(entry.employee),
                    "gross_pay": entry.gross_pay,
                    "deductions": entry.deductions,
                    "net_pay": entry.net_pay,
                    "currency": entry.currency,
                }
            )
        report_data = {
            "report_type": "payroll_run",
            "name": f"Payroll Run {run.pk}",
            "generated_at": timezone.now(),
            "headers": ["Employee", "Gross Pay", "Deductions", "Net Pay", "Currency"],
            "rows": rows,
        }
        file_buffer, filename = ReportExportService.to_pdf(report_data)
        response = HttpResponse(file_buffer.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="payroll_run_{run.pk}.pdf"'
        return response

    return HttpResponse(status=400)


def post_payroll_run(request, pk):
    if request.method != "POST":
        return HttpResponse(status=405)
    run = PayrollRun.objects.select_related("organization").get(pk=pk)
    org = run.organization
    if request.user.get_active_organization() != org and not request.user.is_superuser:
        return HttpResponse(status=403)
    service = PayrollService(request.user, org)
    service.post_run(run)
    messages.success(request, "Payroll run posted.")
    return HttpResponseRedirect(reverse("enterprise:payroll_run_list"))


# -----------------------
# Integrations / Webhooks / Observability
# -----------------------
class IntegrationCredentialListView(EnterpriseListView):
    model = IntegrationCredential
    list_display = ("name", "connector_type", "masked_display", "is_active")
    create_url_name = "enterprise:integrationcredential_create"
    update_url_name = "enterprise:integrationcredential_update"
    permission_required = ("enterprise", "integrationcredential", "view")


class IntegrationCredentialCreateView(EnterpriseCreateView):
    model = IntegrationCredential
    form_class = forms.IntegrationCredentialForm
    form_title = "Create Integration Credential"
    success_url_name = "enterprise:integrationcredential_list"
    back_url_name = "enterprise:integrationcredential_list"
    permission_required = ("enterprise", "integrationcredential", "add")


class IntegrationCredentialUpdateView(EnterpriseUpdateView):
    model = IntegrationCredential
    form_class = forms.IntegrationCredentialForm
    form_title = "Edit Integration Credential"
    success_url_name = "enterprise:integrationcredential_list"
    back_url_name = "enterprise:integrationcredential_list"
    permission_required = ("enterprise", "integrationcredential", "change")


class WebhookSubscriptionListView(EnterpriseListView):
    model = WebhookSubscription
    list_display = ("name", "token", "source", "is_active")
    create_url_name = "enterprise:webhooksubscription_create"
    update_url_name = "enterprise:webhooksubscription_update"
    permission_required = ("enterprise", "webhooksubscription", "view")


class WebhookSubscriptionCreateView(EnterpriseCreateView):
    model = WebhookSubscription
    form_class = forms.WebhookSubscriptionForm
    form_title = "Create Webhook Subscription"
    success_url_name = "enterprise:webhooksubscription_list"
    back_url_name = "enterprise:webhooksubscription_list"
    permission_required = ("enterprise", "webhooksubscription", "add")


class WebhookSubscriptionUpdateView(EnterpriseUpdateView):
    model = WebhookSubscription
    form_class = forms.WebhookSubscriptionForm
    form_title = "Edit Webhook Subscription"
    success_url_name = "enterprise:webhooksubscription_list"
    back_url_name = "enterprise:webhooksubscription_list"
    permission_required = ("enterprise", "webhooksubscription", "change")


def webhook_receiver(request, token):
    if request.method != "POST":
        return HttpResponse(status=405)
    sub = WebhookSubscription.objects.filter(token=token, is_active=True).first()
    if not sub:
        return HttpResponse(status=404)
    payload = request.body.decode("utf-8")
    IntegrationEvent.objects.create(
        event_type="webhook.received",
        payload={"raw": payload},
        source_object="WebhookSubscription",
        source_id=str(sub.pk),
    )
    return JsonResponse({"status": "ok"})


class ObservabilityView(PermissionRequiredMixin, UserOrganizationMixin, TemplateView):
    template_name = "enterprise/observability.html"
    permission_required = ("enterprise", "integrationendpoint", "view")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        org = self.get_organization()
        ctx["endpoints"] = IntegrationEndpoint.objects.filter(organization=org)
        ctx["credentials"] = IntegrationCredential.objects.filter(organization=org)
        ctx["webhooks"] = WebhookSubscription.objects.filter(organization=org)
        ctx["recent_events"] = IntegrationEvent.objects.order_by("-created_at")[:20]
        ctx["page_title"] = "Observability"
        return ctx
