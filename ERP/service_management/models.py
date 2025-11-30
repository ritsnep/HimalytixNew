# service_management/models.py
"""
Service management models for SaaS vertical playbook
Supports device lifecycle, service contracts, warranty tracking, and hardware RMAs
"""
from django.db import models
from django.utils import timezone
from decimal import Decimal
from usermanagement.models import Organization
from accounting.models import ChartOfAccount


class DeviceCategory(models.Model):
    """Categories for hardware devices (routers, servers, IoT devices, etc.)"""
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name='device_categories')
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        app_label = 'service_management'
        unique_together = ('organization', 'code')
        ordering = ['name']
    
    def __str__(self):
        return f"{self.organization.name} - {self.name}"


class DeviceModel(models.Model):
    """Device model/SKU definitions"""
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name='device_models')
    category = models.ForeignKey(DeviceCategory, on_delete=models.PROTECT, related_name='models')
    
    model_number = models.CharField(max_length=100)
    manufacturer = models.CharField(max_length=150)
    model_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Warranty
    standard_warranty_months = models.IntegerField(default=12)
    
    # Pricing
    cost_price = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    sale_price = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    
    # Technical specs
    specifications = models.JSONField(default=dict, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'service_management'
        unique_together = ('organization', 'model_number')
        ordering = ['manufacturer', 'model_name']
    
    def __str__(self):
        return f"{self.manufacturer} {self.model_name} ({self.model_number})"


class DeviceLifecycle(models.Model):
    """Track individual device instances through their lifecycle"""
    LIFECYCLE_STATES = [
        ('inventory', 'In Inventory'),
        ('provisioning', 'Provisioning'),
        ('deployed', 'Deployed/Active'),
        ('maintenance', 'Under Maintenance'),
        ('rma', 'RMA'),
        ('repair', 'In Repair'),
        ('retired', 'Retired'),
        ('disposed', 'Disposed'),
    ]
    
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name='devices')
    device_model = models.ForeignKey(DeviceModel, on_delete=models.PROTECT, related_name='instances')
    
    serial_number = models.CharField(max_length=150, unique=True)
    asset_tag = models.CharField(max_length=100, blank=True)
    
    # Lifecycle state
    state = models.CharField(max_length=20, choices=LIFECYCLE_STATES, default='inventory')
    state_changed_at = models.DateTimeField(default=timezone.now)
    
    # Deployment details
    customer_id = models.IntegerField(null=True, blank=True)  # FK to Customer
    deployed_date = models.DateField(null=True, blank=True)
    deployment_location = models.CharField(max_length=200, blank=True)
    
    # Service contract link
    service_contract = models.ForeignKey(
        'ServiceContract',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='devices'
    )
    
    # Warranty tracking
    warranty_start_date = models.DateField(null=True, blank=True)
    warranty_end_date = models.DateField(null=True, blank=True)
    extended_warranty = models.BooleanField(default=False)
    
    # Telemetry/IoT integration
    last_telemetry_received = models.DateTimeField(null=True, blank=True)
    telemetry_status = models.CharField(max_length=50, blank=True)  # online, offline, degraded
    firmware_version = models.CharField(max_length=50, blank=True)
    
    # Metadata
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'service_management'
        indexes = [
            models.Index(fields=['organization', 'state']),
            models.Index(fields=['customer_id', 'state']),
            models.Index(fields=['serial_number']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.device_model.model_number} - SN: {self.serial_number} ({self.state})"
    
    @property
    def is_under_warranty(self):
        """Check if device is still under warranty"""
        if not self.warranty_end_date:
            return False
        return timezone.now().date() <= self.warranty_end_date


class DeviceStateHistory(models.Model):
    """Audit trail of device state changes"""
    device = models.ForeignKey(DeviceLifecycle, on_delete=models.CASCADE, related_name='state_history')
    from_state = models.CharField(max_length=20)
    to_state = models.CharField(max_length=20)
    changed_by = models.IntegerField()  # User ID
    change_date = models.DateTimeField(default=timezone.now)
    reason = models.TextField(blank=True)
    
    class Meta:
        app_label = 'service_management'
        ordering = ['-change_date']
    
    def __str__(self):
        return f"{self.device.serial_number}: {self.from_state} → {self.to_state}"


class ServiceContract(models.Model):
    """Service contracts for SaaS/support agreements"""
    CONTRACT_TYPES = [
        ('basic', 'Basic Support'),
        ('standard', 'Standard Support'),
        ('premium', 'Premium Support'),
        ('enterprise', 'Enterprise Support'),
        ('custom', 'Custom Agreement'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]
    
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name='service_contracts')
    contract_number = models.CharField(max_length=50, unique=True)
    customer_id = models.IntegerField()  # FK to Customer
    
    contract_type = models.CharField(max_length=20, choices=CONTRACT_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Dates
    start_date = models.DateField()
    end_date = models.DateField()
    renewal_date = models.DateField(null=True, blank=True)
    auto_renew = models.BooleanField(default=True)
    
    # Pricing
    annual_value = models.DecimalField(max_digits=19, decimal_places=4)
    billing_frequency = models.CharField(max_length=20, default='annual')  # monthly, quarterly, annual
    
    # SLA terms
    response_time_hours = models.IntegerField(default=24)
    resolution_time_hours = models.IntegerField(null=True, blank=True)
    uptime_guarantee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('99.9'))
    
    # Revenue recognition
    revenue_account = models.ForeignKey(
        ChartOfAccount,
        on_delete=models.PROTECT,
        related_name='service_contract_revenue',
        null=True,
        blank=True
    )
    
    # Terms and conditions
    terms = models.TextField(blank=True)
    
    # Metadata
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'service_management'
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['customer_id', 'status']),
            models.Index(fields=['end_date', 'auto_renew']),
        ]
        ordering = ['-start_date']
    
    def __str__(self):
        return f"{self.contract_number} - {self.contract_type}"
    
    @property
    def is_active(self):
        """Check if contract is currently active"""
        today = timezone.now().date()
        return (
            self.status == 'active' and
            self.start_date <= today <= self.end_date
        )


class ServiceTicket(models.Model):
    """Service tickets linked to contracts and devices"""
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('waiting_customer', 'Waiting on Customer'),
        ('escalated', 'Escalated'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    ticket_number = models.CharField(max_length=50, unique=True)
    
    service_contract = models.ForeignKey(
        ServiceContract,
        on_delete=models.PROTECT,
        related_name='tickets',
        null=True,
        blank=True
    )
    device = models.ForeignKey(
        DeviceLifecycle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='service_tickets'
    )
    
    customer_id = models.IntegerField()
    
    # Ticket details
    subject = models.CharField(max_length=200)
    description = models.TextField()
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='open')
    
    # Assignment
    assigned_to = models.IntegerField(null=True, blank=True)  # User ID
    assigned_date = models.DateTimeField(null=True, blank=True)
    
    # SLA tracking
    created_date = models.DateTimeField(default=timezone.now)
    first_response_date = models.DateTimeField(null=True, blank=True)
    resolution_date = models.DateTimeField(null=True, blank=True)
    closed_date = models.DateTimeField(null=True, blank=True)
    
    sla_breach = models.BooleanField(default=False)
    
    # Resolution
    resolution_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'service_management'
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['customer_id', 'status']),
            models.Index(fields=['priority', 'status']),
        ]
        ordering = ['-created_date']
    
    def __str__(self):
        return f"{self.ticket_number} - {self.subject}"


class WarrantyPool(models.Model):
    """Track warranty inventory and replacement devices"""
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name='warranty_pools')
    device_model = models.ForeignKey(DeviceModel, on_delete=models.PROTECT, related_name='warranty_pools')
    
    pool_name = models.CharField(max_length=150)
    location = models.CharField(max_length=200)  # Warehouse location
    
    # Quantities
    available_quantity = models.IntegerField(default=0)
    allocated_quantity = models.IntegerField(default=0)
    minimum_quantity = models.IntegerField(default=0)
    
    # Costs
    average_unit_cost = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'service_management'
        unique_together = ('organization', 'device_model', 'pool_name')
        ordering = ['device_model', 'pool_name']
    
    def __str__(self):
        return f"{self.pool_name} - {self.device_model.model_number} (Avail: {self.available_quantity})"
    
    @property
    def needs_replenishment(self):
        """Check if pool needs replenishment"""
        return self.available_quantity < self.minimum_quantity


class RMAHardware(models.Model):
    """RMA specifically for hardware devices (extends general RMA functionality)"""
    STATUS_CHOICES = [
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('device_shipped', 'Device Shipped to Depot'),
        ('received', 'Received at Depot'),
        ('diagnosing', 'Under Diagnosis'),
        ('repairing', 'Repairing'),
        ('replacement_shipped', 'Replacement Shipped'),
        ('completed', 'Completed'),
        ('closed', 'Closed'),
    ]
    
    FAILURE_TYPES = [
        ('doa', 'Dead on Arrival'),
        ('hardware_failure', 'Hardware Failure'),
        ('software_issue', 'Software/Firmware Issue'),
        ('physical_damage', 'Physical Damage'),
        ('intermittent', 'Intermittent Issue'),
        ('user_error', 'User Error'),
    ]
    
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    rma_number = models.CharField(max_length=50, unique=True)
    
    device = models.ForeignKey(DeviceLifecycle, on_delete=models.PROTECT, related_name='rmas')
    service_contract = models.ForeignKey(
        ServiceContract,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='device_rmas'
    )
    service_ticket = models.ForeignKey(
        ServiceTicket,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='device_rmas'
    )
    
    customer_id = models.IntegerField()
    
    # RMA details
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='requested')
    failure_type = models.CharField(max_length=30, choices=FAILURE_TYPES)
    failure_description = models.TextField()
    
    # Dates
    requested_date = models.DateTimeField(default=timezone.now)
    approved_date = models.DateTimeField(null=True, blank=True)
    received_date = models.DateTimeField(null=True, blank=True)
    completed_date = models.DateTimeField(null=True, blank=True)
    
    # Warranty coverage
    is_under_warranty = models.BooleanField(default=False)
    warranty_claim_number = models.CharField(max_length=100, blank=True)
    
    # Replacement
    replacement_device = models.ForeignKey(
        DeviceLifecycle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rma_replacements'
    )
    replacement_shipped_date = models.DateTimeField(null=True, blank=True)
    
    # Repair disposition
    repair_action = models.CharField(max_length=50, blank=True)  # replace, repair, credit
    repair_cost = models.DecimalField(max_digits=19, decimal_places=4, null=True, blank=True)
    
    # Tracking
    return_tracking_number = models.CharField(max_length=100, blank=True)
    replacement_tracking_number = models.CharField(max_length=100, blank=True)
    
    # Resolution
    resolution_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'service_management'
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['device', 'status']),
            models.Index(fields=['customer_id']),
        ]
        ordering = ['-requested_date']
    
    def __str__(self):
        return f"{self.rma_number} - {self.device.serial_number} ({self.status})"


class DeviceProvisioningTemplate(models.Model):
    """Provisioning templates for automated device setup"""
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    template_name = models.CharField(max_length=150)
    device_model = models.ForeignKey(
        DeviceModel,
        on_delete=models.PROTECT,
        related_name='provisioning_templates',
        null=True,
        blank=True
    )
    
    # Provisioning steps
    configuration_script = models.TextField(help_text="Automated configuration commands")
    firmware_url = models.URLField(blank=True)
    required_firmware_version = models.CharField(max_length=50, blank=True)
    
    # Metadata
    provisioning_metadata = models.JSONField(default=dict, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'service_management'
        ordering = ['template_name']
    
    def __str__(self):
        return f"{self.template_name}"


class DeviceProvisioningLog(models.Model):
    """Log of device provisioning activities"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]
    
    device = models.ForeignKey(DeviceLifecycle, on_delete=models.CASCADE, related_name='provisioning_logs')
    template = models.ForeignKey(
        DeviceProvisioningTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    provisioning_date = models.DateTimeField(default=timezone.now)
    provisioned_by = models.IntegerField()  # User ID
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    
    # Results
    firmware_version_applied = models.CharField(max_length=50, blank=True)
    configuration_applied = models.TextField(blank=True)
    error_log = models.TextField(blank=True)
    
    completion_date = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        app_label = 'service_management'
        ordering = ['-provisioning_date']
    
    def __str__(self):
        return f"{self.device.serial_number} - {self.status} on {self.provisioning_date}"
