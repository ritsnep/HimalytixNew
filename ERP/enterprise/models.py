from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


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


class PayrollEntry(OrganizationScopedModel):
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

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class FixedAsset(OrganizationScopedModel):
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

    class Meta:
        unique_together = ("organization", "asset_code")
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.asset_code} - {self.name}"


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
