from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from accounting.models import ChartOfAccount


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class OrganizationScopedModel(TimeStampedModel):
    organization = models.ForeignKey(
        'usermanagement.Organization',
        on_delete=models.CASCADE,
        related_name="%(class)ss",
    )

    class Meta(TimeStampedModel.Meta):
        abstract = True


class Department(OrganizationScopedModel):
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=50, blank=True)

    class Meta:
        unique_together = ("organization", "code")
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})" if self.code else self.name


class Position(OrganizationScopedModel):
    title = models.CharField(max_length=150)
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="positions",
        null=True,
        blank=True,
    )
    grade = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["title"]

    def __str__(self) -> str:
        return self.title


class Employee(OrganizationScopedModel):
    class EmploymentType(models.TextChoices):
        FULL_TIME = "full_time", _("Full Time")
        PART_TIME = "part_time", _("Part Time")
        CONTRACT = "contract", _("Contract")
        INTERN = "intern", _("Intern")

    class EmploymentStatus(models.TextChoices):
        ACTIVE = "active", _("Active")
        ON_LEAVE = "on_leave", _("On Leave")
        TERMINATED = "terminated", _("Terminated")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
    )
    employee_id = models.CharField(max_length=50)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="employees",
        null=True,
        blank=True,
    )
    position = models.ForeignKey(
        Position,
        on_delete=models.PROTECT,
        related_name="employees",
        null=True,
        blank=True,
    )
    manager = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reports",
    )
    employment_type = models.CharField(
        max_length=20,
        choices=EmploymentType.choices,
        default=EmploymentType.FULL_TIME,
    )
    status = models.CharField(
        max_length=20,
        choices=EmploymentStatus.choices,
        default=EmploymentStatus.ACTIVE,
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = ("organization", "employee_id")
        ordering = ["last_name", "first_name"]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}"


class PayrollCycle(OrganizationScopedModel):
    class PayrollStatus(models.TextChoices):
        DRAFT = "draft", _("Draft")
        APPROVED = "approved", _("Approved")
        POSTED = "posted", _("Posted")

    name = models.CharField(max_length=120)
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=PayrollStatus.choices,
        default=PayrollStatus.DRAFT,
    )

    class Meta:
        ordering = ["-period_start"]

    def __str__(self) -> str:
        return f"{self.name} ({self.period_start} - {self.period_end})"


class PayComponent(OrganizationScopedModel):
    class ComponentType(models.TextChoices):
        EARNING = "earning", _("Earning")
        DEDUCTION = "deduction", _("Deduction")
        TAX = "tax", _("Tax")
        BENEFIT = "benefit", _("Benefit")

    class AmountType(models.TextChoices):
        FIXED = "fixed", _("Fixed")
        PERCENT = "percent", _("Percent of base")

    code = models.CharField(max_length=50)
    name = models.CharField(max_length=150)
    component_type = models.CharField(
        max_length=20,
        choices=ComponentType.choices,
        default=ComponentType.EARNING,
    )
    amount_type = models.CharField(
        max_length=20,
        choices=AmountType.choices,
        default=AmountType.FIXED,
    )
    amount_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    account = models.ForeignKey(
        ChartOfAccount,
        on_delete=models.PROTECT,
        related_name="pay_components",
    )
    is_taxable = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("organization", "code")
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class PayrollRun(OrganizationScopedModel):
    class RunStatus(models.TextChoices):
        DRAFT = "draft", _("Draft")
        APPROVED = "approved", _("Approved")
        POSTED = "posted", _("Posted")

    payroll_cycle = models.ForeignKey(
        PayrollCycle,
        on_delete=models.PROTECT,
        related_name="runs",
        null=True,
        blank=True,
    )
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=RunStatus.choices,
        default=RunStatus.DRAFT,
    )
    expense_account = models.ForeignKey(
        ChartOfAccount,
        on_delete=models.PROTECT,
        related_name="payroll_expense_runs",
    )
    liability_account = models.ForeignKey(
        ChartOfAccount,
        on_delete=models.PROTECT,
        related_name="payroll_liability_runs",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_payroll_runs",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-period_end"]

    def __str__(self) -> str:
        return f"Payroll {self.period_start} - {self.period_end}"


class PayrollRunLine(OrganizationScopedModel):
    payroll_run = models.ForeignKey(
        PayrollRun,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="payroll_run_lines",
    )
    component = models.ForeignKey(
        PayComponent,
        on_delete=models.PROTECT,
        related_name="payroll_run_lines",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["employee__last_name", "component__name"]

    def __str__(self) -> str:
        return f"{self.employee} - {self.component}"


class PayrollEntry(OrganizationScopedModel):
    payroll_run = models.ForeignKey(
        "PayrollRun",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entries",
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="payroll_entries",
    )
    payroll_cycle = models.ForeignKey(
        PayrollCycle,
        on_delete=models.CASCADE,
        related_name="entries",
    )
    gross_pay = models.DecimalField(max_digits=12, decimal_places=2)
    deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_pay = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")

    class Meta:
        ordering = ["employee__last_name", "employee__first_name"]

    def __str__(self) -> str:
        return f"{self.employee} - {self.payroll_cycle}"


class LeaveRequest(OrganizationScopedModel):
    class LeaveStatus(models.TextChoices):
        DRAFT = "draft", _("Draft")
        PENDING = "pending", _("Pending Approval")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Rejected")

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="leave_requests",
    )
    leave_type = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=LeaveStatus.choices,
        default=LeaveStatus.DRAFT,
    )
    reason = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"{self.employee} - {self.leave_type}"


class AttendanceRecord(OrganizationScopedModel):
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    work_date = models.DateField()
    hours_worked = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    status = models.CharField(max_length=50, default="present")

    class Meta:
        unique_together = ("employee", "work_date")
        ordering = ["-work_date"]

    def __str__(self) -> str:
        return f"{self.employee} - {self.work_date}"


class BenefitEnrollment(OrganizationScopedModel):
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="benefits",
    )
    benefit_name = models.CharField(max_length=150)
    contribution = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    employer_contribution = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self) -> str:
        return f"{self.employee} - {self.benefit_name}"


class FixedAssetCategory(OrganizationScopedModel):
    class DepreciationMethod(models.TextChoices):
        STRAIGHT_LINE = "straight_line", _("Straight Line")
        DECLINING_BALANCE = "declining_balance", _("Declining Balance")

    name = models.CharField(max_length=120)
    depreciation_method = models.CharField(
        max_length=50,
        choices=DepreciationMethod.choices,
        default=DepreciationMethod.STRAIGHT_LINE,
    )
    useful_life_months = models.PositiveIntegerField(default=60)
    salvage_value_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    asset_account = models.ForeignKey(
        ChartOfAccount,
        on_delete=models.PROTECT,
        related_name="enterprise_asset_accounts",
        help_text="Balance sheet account to hold the asset cost.",
        null=True,
        blank=True,
    )
    depreciation_expense_account = models.ForeignKey(
        ChartOfAccount,
        on_delete=models.PROTECT,
        related_name="enterprise_depreciation_expense_accounts",
        help_text="Income statement account for depreciation expense.",
        null=True,
        blank=True,
    )
    accumulated_depreciation_account = models.ForeignKey(
        ChartOfAccount,
        on_delete=models.PROTECT,
        related_name="enterprise_accumulated_depreciation_accounts",
        help_text="Balance sheet contra-asset for accumulated depreciation.",
        null=True,
        blank=True,
    )
    disposal_gain_account = models.ForeignKey(
        ChartOfAccount,
        on_delete=models.PROTECT,
        related_name="enterprise_disposal_gain_accounts",
        null=True,
        blank=True,
        help_text="Optional account for gains on disposal.",
    )
    disposal_loss_account = models.ForeignKey(
        ChartOfAccount,
        on_delete=models.PROTECT,
        related_name="enterprise_disposal_loss_accounts",
        null=True,
        blank=True,
        help_text="Optional account for losses on disposal.",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class FixedAsset(OrganizationScopedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        DISPOSED = "disposed", _("Disposed")

    name = models.CharField(max_length=150)
    asset_code = models.CharField(max_length=50)
    category = models.ForeignKey(
        FixedAssetCategory,
        on_delete=models.PROTECT,
        related_name="assets",
    )
    acquisition_date = models.DateField()
    acquisition_cost = models.DecimalField(max_digits=14, decimal_places=2)
    salvage_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    useful_life_months = models.PositiveIntegerField(default=60)
    location = models.CharField(max_length=150, blank=True)
    custodian = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_assets",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    disposed_at = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = ("organization", "asset_code")
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.asset_code} - {self.name}"

    @property
    def accumulated_depreciation(self):
        from django.db.models import Sum

        total = (
            self.depreciation_schedule.filter(posted_journal=True)
            .aggregate(total=Sum("depreciation_amount"))
            .get("total")
            or Decimal("0")
        )
        return total

    @property
    def book_value(self):
        return max(self.acquisition_cost - self.accumulated_depreciation, Decimal("0"))


class AssetDepreciationSchedule(OrganizationScopedModel):
    asset = models.ForeignKey(
        FixedAsset,
        on_delete=models.CASCADE,
        related_name="depreciation_schedule",
    )
    period_start = models.DateField()
    period_end = models.DateField()
    depreciation_amount = models.DecimalField(max_digits=14, decimal_places=2)
    posted_journal = models.BooleanField(default=False)

    class Meta:
        ordering = ["period_start"]

    def __str__(self) -> str:
        return f"{self.asset} - {self.period_start}"


class BillOfMaterial(OrganizationScopedModel):
    name = models.CharField(max_length=150)
    product_name = models.CharField(max_length=150)
    revision = models.CharField(max_length=20, default="A")

    class Meta:
        unique_together = ("organization", "product_name", "revision")

    def __str__(self) -> str:
        return f"{self.product_name} (Rev {self.revision})"


class BillOfMaterialItem(models.Model):
    bill_of_material = models.ForeignKey(
        BillOfMaterial,
        on_delete=models.CASCADE,
        related_name="items",
    )
    component_name = models.CharField(max_length=150)
    quantity = models.DecimalField(max_digits=12, decimal_places=4)
    uom = models.CharField(max_length=50, default="unit")

    def __str__(self) -> str:
        return f"{self.component_name} x {self.quantity}"


class WorkOrder(OrganizationScopedModel):
    class WorkOrderStatus(models.TextChoices):
        PLANNED = "planned", _("Planned")
        IN_PROGRESS = "in_progress", _("In Progress")
        COMPLETED = "completed", _("Completed")
        CANCELLED = "cancelled", _("Cancelled")

    work_order_number = models.CharField(max_length=50)
    bill_of_material = models.ForeignKey(
        BillOfMaterial,
        on_delete=models.PROTECT,
        related_name="work_orders",
    )
    quantity_to_produce = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=WorkOrderStatus.choices,
        default=WorkOrderStatus.PLANNED,
    )
    planned_start = models.DateField(null=True, blank=True)
    planned_end = models.DateField(null=True, blank=True)
    routing_instructions = models.TextField(blank=True)

    class Meta:
        unique_together = ("organization", "work_order_number")
        ordering = ["-planned_start"]

    def __str__(self) -> str:
        return self.work_order_number


class WorkCenter(OrganizationScopedModel):
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=50)
    capacity_per_day = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("organization", "code")
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class Routing(OrganizationScopedModel):
    name = models.CharField(max_length=150)
    work_center = models.ForeignKey(
        WorkCenter,
        on_delete=models.PROTECT,
        related_name="routings",
    )
    standard_duration_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class WorkOrderOperation(OrganizationScopedModel):
    work_order = models.ForeignKey(
        WorkOrder,
        on_delete=models.CASCADE,
        related_name="operations",
    )
    routing = models.ForeignKey(
        Routing,
        on_delete=models.PROTECT,
        related_name="operations",
    )
    sequence = models.PositiveIntegerField(default=1)
    planned_start = models.DateTimeField(null=True, blank=True)
    planned_end = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=WorkOrder.WorkOrderStatus.choices,
        default=WorkOrder.WorkOrderStatus.PLANNED,
    )

    class Meta:
        ordering = ["sequence"]

    def __str__(self) -> str:
        return f"{self.work_order} - {self.routing}"


class WorkOrderMaterial(models.Model):
    work_order = models.ForeignKey(
        WorkOrder,
        on_delete=models.CASCADE,
        related_name="materials",
    )
    component_name = models.CharField(max_length=150)
    quantity_required = models.DecimalField(max_digits=12, decimal_places=4)
    quantity_issued = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    uom = models.CharField(max_length=50, default="unit")

    def __str__(self) -> str:
        return f"{self.work_order} - {self.component_name}"


class CRMLead(OrganizationScopedModel):
    name = models.CharField(max_length=150)
    source = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=50, default="new")
    probability = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name


class Opportunity(OrganizationScopedModel):
    lead = models.ForeignKey(
        CRMLead,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="opportunities",
    )
    name = models.CharField(max_length=150)
    stage = models.CharField(max_length=50, default="qualification")
    expected_close = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")
    probability = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        ordering = ["-expected_close"]

    def __str__(self) -> str:
        return self.name


class Campaign(OrganizationScopedModel):
    name = models.CharField(max_length=150)
    channel = models.CharField(max_length=100, blank=True)
    budget_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self) -> str:
        return self.name


class Budget(OrganizationScopedModel):
    class BudgetStatus(models.TextChoices):
        DRAFT = "draft", _("Draft")
        SUBMITTED = "submitted", _("Submitted")
        APPROVED = "approved", _("Approved")

    name = models.CharField(max_length=150)
    fiscal_year = models.CharField(max_length=10)
    revision_label = models.CharField(max_length=50, default="v1")
    revision_of = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revisions",
    )
    status = models.CharField(
        max_length=20,
        choices=BudgetStatus.choices,
        default=BudgetStatus.DRAFT,
    )

    class Meta:
        ordering = ["-fiscal_year", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.fiscal_year})"


class BudgetLine(models.Model):
    budget = models.ForeignKey(
        Budget,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="budget_lines",
    )
    project_name = models.CharField(max_length=150, blank=True)
    account_code = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=14, decimal_places=2)

    def __str__(self) -> str:
        return f"{self.account_code} - {self.amount}"


class IntegrationEndpoint(OrganizationScopedModel):
    class ConnectorType(models.TextChoices):
        BANK_FEED = "bank_feed", _("Bank Feed")
        PAYMENT_GATEWAY = "payment_gateway", _("Payment Gateway")
        ECOMMERCE = "ecommerce", _("E-commerce")
        LOGISTICS = "logistics", _("Logistics")
        POS = "pos", _("Point of Sale")

    name = models.CharField(max_length=150)
    connector_type = models.CharField(
        max_length=50,
        choices=ConnectorType.choices,
    )
    base_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.connector_type})"


class IntegrationCredential(OrganizationScopedModel):
    """Stores connector credentials (vaulted/opaque)."""

    name = models.CharField(max_length=150)
    connector_type = models.CharField(
        max_length=50,
        choices=IntegrationEndpoint.ConnectorType.choices,
    )
    credential_blob = models.JSONField(default=dict, blank=True)
    masked_display = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("organization", "name")

    def __str__(self) -> str:
        return self.name


class WebhookSubscription(OrganizationScopedModel):
    """Inbound webhook endpoint registration."""

    name = models.CharField(max_length=150)
    token = models.UUIDField(unique=True)
    source = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class POSDevice(OrganizationScopedModel):
    identifier = models.CharField(max_length=100)
    location = models.CharField(max_length=150, blank=True)
    status = models.CharField(max_length=50, default="active")

    class Meta:
        unique_together = ("organization", "identifier")

    def __str__(self) -> str:
        return self.identifier


class LocaleConfig(OrganizationScopedModel):
    locale_code = models.CharField(max_length=20, default="en-US")
    timezone = models.CharField(max_length=50, default="UTC")
    default_currency = models.CharField(max_length=10, default="USD")
    tax_region = models.CharField(max_length=100, blank=True)
    enable_e_invoicing = models.BooleanField(default=False)

    class Meta:
        unique_together = ("organization", "locale_code")

    def __str__(self) -> str:
        return f"{self.organization} - {self.locale_code}"


class TaxRegime(OrganizationScopedModel):
    name = models.CharField(max_length=150)
    country = models.CharField(max_length=50, blank=True)
    region = models.CharField(max_length=50, blank=True)
    e_invoice_format = models.CharField(max_length=100, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


# ---------- Manufacturing Enhancements ----------
class BOMRevision(OrganizationScopedModel):
    """BOM revision control for engineer-to-order and change management"""
    bill_of_material = models.ForeignKey(
        BillOfMaterial,
        on_delete=models.CASCADE,
        related_name="revisions",
    )
    revision_number = models.CharField(max_length=20)
    effective_date = models.DateField()
    obsolete_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    change_reason = models.TextField(blank=True)
    changed_by = models.IntegerField(null=True, blank=True)  # User ID
    approved_by = models.IntegerField(null=True, blank=True)  # User ID
    approved_date = models.DateTimeField(null=True, blank=True)
    eco_number = models.CharField(max_length=50, blank=True)  # Engineering Change Order
    notes = models.TextField(blank=True)
    
    class Meta:
        unique_together = ("bill_of_material", "revision_number")
        ordering = ["-effective_date"]
    
    def __str__(self) -> str:
        return f"{self.bill_of_material.product_name} - Rev {self.revision_number}"


class QCCheckpoint(OrganizationScopedModel):
    """Quality control checkpoints in routing"""
    CHECKPOINT_TYPES = [
        ('incoming', 'Incoming Material Inspection'),
        ('in_process', 'In-Process Inspection'),
        ('final', 'Final Inspection'),
        ('sampling', 'Statistical Sampling'),
    ]
    
    TEST_METHODS = [
        ('visual', 'Visual Inspection'),
        ('dimensional', 'Dimensional Measurement'),
        ('functional', 'Functional Test'),
        ('destructive', 'Destructive Test'),
        ('non_destructive', 'Non-Destructive Test'),
    ]
    
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=50)
    checkpoint_type = models.CharField(max_length=20, choices=CHECKPOINT_TYPES)
    test_method = models.CharField(max_length=30, choices=TEST_METHODS)
    specification = models.TextField()  # Acceptance criteria
    sample_size = models.IntegerField(default=1)
    work_center = models.ForeignKey(
        WorkCenter,
        on_delete=models.PROTECT,
        related_name="qc_checkpoints",
        null=True,
        blank=True,
    )
    routing = models.ForeignKey(
        Routing,
        on_delete=models.CASCADE,
        related_name="qc_checkpoints",
        null=True,
        blank=True,
    )
    is_mandatory = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ("organization", "code")
        ordering = ["name"]
    
    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class QCInspectionRecord(OrganizationScopedModel):
    """Record of quality inspections"""
    RESULT_CHOICES = [
        ('pass', 'Pass'),
        ('fail', 'Fail'),
        ('conditional', 'Conditional Pass'),
    ]
    
    inspection_number = models.CharField(max_length=50, unique=True)
    qc_checkpoint = models.ForeignKey(
        QCCheckpoint,
        on_delete=models.PROTECT,
        related_name="inspections",
    )
    work_order = models.ForeignKey(
        WorkOrder,
        on_delete=models.PROTECT,
        related_name="qc_inspections",
        null=True,
        blank=True,
    )
    batch_number = models.CharField(max_length=100, blank=True)
    inspector_id = models.IntegerField()  # User ID
    inspection_date = models.DateTimeField()
    result = models.CharField(max_length=20, choices=RESULT_CHOICES)
    quantity_inspected = models.DecimalField(max_digits=12, decimal_places=4)
    quantity_passed = models.DecimalField(max_digits=12, decimal_places=4)
    quantity_failed = models.DecimalField(max_digits=12, decimal_places=4)
    measurements = models.JSONField(default=dict, blank=True)  # Actual measurements
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ["-inspection_date"]
    
    def __str__(self) -> str:
        return f"{self.inspection_number} - {self.result}"


class NCR(OrganizationScopedModel):
    """Non-Conformance Report"""
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('investigating', 'Under Investigation'),
        ('corrective_action', 'Corrective Action'),
        ('closed', 'Closed'),
        ('rejected', 'Rejected'),
    ]
    
    SEVERITY_CHOICES = [
        ('critical', 'Critical'),
        ('major', 'Major'),
        ('minor', 'Minor'),
    ]
    
    ncr_number = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='open')
    work_order = models.ForeignKey(
        WorkOrder,
        on_delete=models.PROTECT,
        related_name="ncrs",
        null=True,
        blank=True,
    )
    qc_inspection = models.ForeignKey(
        QCInspectionRecord,
        on_delete=models.SET_NULL,
        related_name="ncrs",
        null=True,
        blank=True,
    )
    reported_by = models.IntegerField()  # User ID
    reported_date = models.DateTimeField()
    assigned_to = models.IntegerField(null=True, blank=True)  # User ID
    root_cause = models.TextField(blank=True)
    corrective_action = models.TextField(blank=True)
    preventive_action = models.TextField(blank=True)
    closed_by = models.IntegerField(null=True, blank=True)  # User ID
    closed_date = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ["-reported_date"]
    
    def __str__(self) -> str:
        return f"{self.ncr_number} - {self.title} ({self.severity})"


class ProductionCalendar(OrganizationScopedModel):
    """Production calendar with shift schedules and holidays"""
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=50)
    work_center = models.ForeignKey(
        WorkCenter,
        on_delete=models.CASCADE,
        related_name="calendars",
        null=True,
        blank=True,
    )
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ("organization", "code")
        ordering = ["name"]
    
    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class Shift(models.Model):
    """Shift definition for production calendar"""
    DAYS_OF_WEEK = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]
    
    calendar = models.ForeignKey(
        ProductionCalendar,
        on_delete=models.CASCADE,
        related_name="shifts",
    )
    name = models.CharField(max_length=100)
    day_of_week = models.IntegerField(choices=DAYS_OF_WEEK)
    start_time = models.TimeField()
    end_time = models.TimeField()
    capacity_hours = models.DecimalField(max_digits=6, decimal_places=2)
    
    class Meta:
        ordering = ["day_of_week", "start_time"]
    
    def __str__(self) -> str:
        return f"{self.calendar.name} - {self.name} ({self.get_day_of_week_display()})"


class ProductionHoliday(models.Model):
    """Holiday/shutdown dates for production calendar"""
    calendar = models.ForeignKey(
        ProductionCalendar,
        on_delete=models.CASCADE,
        related_name="holidays",
    )
    name = models.CharField(max_length=150)
    holiday_date = models.DateField()
    is_recurring = models.BooleanField(default=False)
    
    class Meta:
        ordering = ["holiday_date"]
    
    def __str__(self) -> str:
        return f"{self.calendar.name} - {self.name} ({self.holiday_date})"


class YieldTracking(OrganizationScopedModel):
    """Track actual vs planned yield for work orders"""
    work_order = models.ForeignKey(
        WorkOrder,
        on_delete=models.CASCADE,
        related_name="yield_tracking",
    )
    operation = models.ForeignKey(
        WorkOrderOperation,
        on_delete=models.CASCADE,
        related_name="yields",
        null=True,
        blank=True,
    )
    planned_quantity = models.DecimalField(max_digits=12, decimal_places=4)
    actual_quantity = models.DecimalField(max_digits=12, decimal_places=4)
    scrap_quantity = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    rework_quantity = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    yield_percentage = models.DecimalField(max_digits=5, decimal_places=2)  # Auto-calculated
    scrap_cost = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    recorded_by = models.IntegerField()  # User ID
    recorded_date = models.DateTimeField()
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ["-recorded_date"]
    
    def save(self, *args, **kwargs):
        # Auto-calculate yield percentage
        if self.planned_quantity > 0:
            self.yield_percentage = (self.actual_quantity / self.planned_quantity) * 100
        super().save(*args, **kwargs)
    
    def __str__(self) -> str:
        return f"{self.work_order.work_order_number} - Yield: {self.yield_percentage}%"


class WorkOrderCosting(OrganizationScopedModel):
    """Track actual costs vs standard costs for work orders"""
    work_order = models.OneToOneField(
        WorkOrder,
        on_delete=models.CASCADE,
        related_name="costing",
    )
    standard_material_cost = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    actual_material_cost = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    standard_labor_cost = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    actual_labor_cost = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    standard_overhead_cost = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    actual_overhead_cost = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    variance_material = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    variance_labor = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    variance_overhead = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    updated_date = models.DateTimeField(auto_now=True)
    
    @property
    def total_standard_cost(self):
        return self.standard_material_cost + self.standard_labor_cost + self.standard_overhead_cost
    
    @property
    def total_actual_cost(self):
        return self.actual_material_cost + self.actual_labor_cost + self.actual_overhead_cost
    
    @property
    def total_variance(self):
        return self.variance_material + self.variance_labor + self.variance_overhead
    
    def __str__(self) -> str:
        return f"{self.work_order.work_order_number} - Costing"

