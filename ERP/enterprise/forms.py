from django import forms

from .models import (
    PayComponent,
    PayrollRun,
    PayrollRunLine,
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
)
from accounting.forms_mixin import BootstrapFormMixin


class DepartmentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Department
        fields = ["name", "code"]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
        }


class PositionForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Position
        fields = ["title", "department", "grade"]


class EmployeeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Employee
        fields = [
            "employee_id",
            "first_name",
            "last_name",
            "department",
            "position",
            "manager",
            "employment_type",
            "status",
            "start_date",
            "end_date",
            "user",
        ]


class PayrollCycleForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PayrollCycle
        fields = ["name", "period_start", "period_end", "status"]


class PayrollEntryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PayrollEntry
        fields = ["payroll_run", "payroll_cycle", "employee", "gross_pay", "deductions", "net_pay", "currency"]


class PayComponentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PayComponent
        fields = [
            "code",
            "name",
            "component_type",
            "amount_type",
            "amount_value",
            "account",
            "is_taxable",
            "is_active",
        ]


class PayrollRunForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PayrollRun
        fields = [
            "payroll_cycle",
            "period_start",
            "period_end",
            "status",
            "expense_account",
            "liability_account",
        ]


class PayrollRunLineForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PayrollRunLine
        fields = ["payroll_run", "employee", "component", "amount", "notes"]


class LeaveRequestForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ["employee", "leave_type", "start_date", "end_date", "status"]


class AttendanceRecordForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AttendanceRecord
        fields = ["employee", "work_date", "hours_worked", "status"]


class BenefitEnrollmentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = BenefitEnrollment
        fields = ["employee", "benefit_name", "contribution", "employer_contribution"]


class FixedAssetCategoryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = FixedAssetCategory
        fields = [
            "name",
            "depreciation_method",
            "useful_life_months",
            "salvage_value_rate",
            "asset_account",
            "depreciation_expense_account",
            "accumulated_depreciation_account",
            "disposal_gain_account",
            "disposal_loss_account",
        ]


class FixedAssetForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = FixedAsset
        fields = [
            "asset_code",
            "name",
            "category",
            "acquisition_date",
            "acquisition_cost",
            "salvage_value",
            "useful_life_months",
            "custodian",
            "location",
        ]


class AssetDepreciationScheduleForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AssetDepreciationSchedule
        fields = ["asset", "period_start", "period_end", "depreciation_amount", "posted_journal"]


class BillOfMaterialForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = BillOfMaterial
        fields = ["name", "product_name", "revision"]


class BillOfMaterialItemForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = BillOfMaterialItem
        fields = ["bill_of_material", "component_name", "quantity", "uom"]


class WorkOrderForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = WorkOrder
        fields = [
            "work_order_number",
            "bill_of_material",
            "quantity_to_produce",
            "status",
            "planned_start",
            "planned_end",
            "routing_instructions",
        ]


class WorkOrderMaterialForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = WorkOrderMaterial
        fields = [
            "work_order",
            "component_name",
            "quantity_required",
            "quantity_issued",
            "uom",
        ]

class WorkCenterForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = WorkCenter
        fields = ["name", "code", "capacity_per_day", "is_active"]


class RoutingForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Routing
        fields = ["name", "work_center", "standard_duration_hours", "is_active"]


class WorkOrderOperationForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = WorkOrderOperation
        fields = ["work_order", "routing", "sequence", "planned_start", "planned_end", "status"]


class CRMLeadForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = CRMLead
        fields = ["name", "source", "status", "probability", "contact_email", "contact_phone"]


class OpportunityForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Opportunity
        fields = [
            "lead",
            "name",
            "stage",
            "expected_close",
            "amount",
            "currency",
            "probability",
        ]


class CampaignForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ["name", "channel", "budget_amount", "start_date", "end_date"]


class BudgetForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Budget
        fields = ["name", "fiscal_year", "revision_label", "revision_of", "status"]


class BudgetLineForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = BudgetLine
        fields = ["budget", "department", "project_name", "account_code", "amount"]


class IntegrationEndpointForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = IntegrationEndpoint
        fields = ["name", "connector_type", "base_url", "is_active", "metadata"]


class IntegrationCredentialForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = IntegrationCredential
        fields = ["name", "connector_type", "credential_blob", "masked_display", "is_active"]


class WebhookSubscriptionForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = WebhookSubscription
        fields = ["name", "token", "source", "is_active"]


class POSDeviceForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = POSDevice
        fields = ["identifier", "location", "status"]


class LocaleConfigForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = LocaleConfig
        fields = ["locale_code", "timezone", "default_currency", "tax_region", "enable_e_invoicing"]


class TaxRegimeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = TaxRegime
        fields = ["name", "country", "region", "e_invoice_format", "metadata", "is_active"]
