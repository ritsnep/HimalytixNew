from django import forms

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


class BaseOrgModelForm(forms.ModelForm):
    """Base ModelForm that filters org-scoped FK querysets."""

    def __init__(self, *args, organization=None, **kwargs):
        self.organization = organization
        super().__init__(*args, **kwargs)
        if organization:
            for field in self.fields.values():
                if isinstance(field, forms.ModelChoiceField):
                    qs = field.queryset
                    if qs is not None and hasattr(qs.model, "organization_id"):
                        field.queryset = qs.filter(organization=organization)

    def save(self, commit=True):
        obj = super().save(commit=False)
        if hasattr(obj, "organization") and obj.organization_id is None:
            obj.organization = self.organization
        if commit:
            obj.save()
        return obj


class DepartmentForm(BaseOrgModelForm):
    class Meta:
        model = Department
        fields = ["name", "code"]


class PositionForm(BaseOrgModelForm):
    class Meta:
        model = Position
        fields = ["title", "department", "grade"]


class EmployeeForm(BaseOrgModelForm):
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


class PayrollCycleForm(BaseOrgModelForm):
    class Meta:
        model = PayrollCycle
        fields = ["name", "period_start", "period_end", "status"]


class PayrollEntryForm(BaseOrgModelForm):
    class Meta:
        model = PayrollEntry
        fields = ["payroll_cycle", "employee", "gross_pay", "deductions", "net_pay", "currency"]


class LeaveRequestForm(BaseOrgModelForm):
    class Meta:
        model = LeaveRequest
        fields = ["employee", "leave_type", "start_date", "end_date", "status"]


class AttendanceRecordForm(BaseOrgModelForm):
    class Meta:
        model = AttendanceRecord
        fields = ["employee", "work_date", "hours_worked", "status"]


class BenefitEnrollmentForm(BaseOrgModelForm):
    class Meta:
        model = BenefitEnrollment
        fields = ["employee", "benefit_name", "contribution", "employer_contribution"]


class FixedAssetCategoryForm(BaseOrgModelForm):
    class Meta:
        model = FixedAssetCategory
        fields = ["name", "depreciation_method", "useful_life_months", "salvage_value_rate"]


class FixedAssetForm(BaseOrgModelForm):
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


class AssetDepreciationScheduleForm(BaseOrgModelForm):
    class Meta:
        model = AssetDepreciationSchedule
        fields = ["asset", "period_start", "period_end", "depreciation_amount", "posted_journal"]


class BillOfMaterialForm(BaseOrgModelForm):
    class Meta:
        model = BillOfMaterial
        fields = ["name", "product_name", "revision"]


class BillOfMaterialItemForm(BaseOrgModelForm):
    class Meta:
        model = BillOfMaterialItem
        fields = ["bill_of_material", "component_name", "quantity", "uom"]


class WorkOrderForm(BaseOrgModelForm):
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


class WorkOrderMaterialForm(BaseOrgModelForm):
    class Meta:
        model = WorkOrderMaterial
        fields = [
            "work_order",
            "component_name",
            "quantity_required",
            "quantity_issued",
            "uom",
        ]


class CRMLeadForm(BaseOrgModelForm):
    class Meta:
        model = CRMLead
        fields = ["name", "source", "status", "probability", "contact_email", "contact_phone"]


class OpportunityForm(BaseOrgModelForm):
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


class CampaignForm(BaseOrgModelForm):
    class Meta:
        model = Campaign
        fields = ["name", "channel", "budget_amount", "start_date", "end_date"]


class BudgetForm(BaseOrgModelForm):
    class Meta:
        model = Budget
        fields = ["name", "fiscal_year", "status"]


class BudgetLineForm(BaseOrgModelForm):
    class Meta:
        model = BudgetLine
        fields = ["budget", "department", "project_name", "account_code", "amount"]


class IntegrationEndpointForm(BaseOrgModelForm):
    class Meta:
        model = IntegrationEndpoint
        fields = ["name", "connector_type", "base_url", "is_active", "metadata"]


class POSDeviceForm(BaseOrgModelForm):
    class Meta:
        model = POSDevice
        fields = ["identifier", "location", "status"]


class LocaleConfigForm(BaseOrgModelForm):
    class Meta:
        model = LocaleConfig
        fields = ["locale_code", "timezone", "default_currency", "tax_region", "enable_e_invoicing"]
