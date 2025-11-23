from django.contrib import messages
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from accounting.mixins import PermissionRequiredMixin, UserOrganizationMixin
from accounting.views.base_views import BaseListView
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
    CRMLead,
    Opportunity,
    Campaign,
    Budget,
    BudgetLine,
    IntegrationEndpoint,
    POSDevice,
    LocaleConfig,
)


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
