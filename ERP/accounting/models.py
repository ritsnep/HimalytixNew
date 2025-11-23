
from datetime import timedelta
from decimal import Decimal

from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.forms import model_to_dict
from django.utils import timezone
from django.contrib.auth import get_user_model
from usermanagement.models import CustomUser, Organization
from django.utils.crypto import get_random_string
from django.db.models import Max, Q, F, CheckConstraint, Sum, UniqueConstraint
import logging
from django.core.exceptions import ValidationError
from django.db import transaction
import re
from django.db.models import JSONField  # If using Django 3.1+, else use from django.contrib.postgres.fields import JSONField
from django.conf import settings

logger = logging.getLogger(__name__)

User = get_user_model()
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class AuditLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=50)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    changes = models.JSONField()
    details = models.TextField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['timestamp']),
        ]

def generate_fiscal_year_id():
    while True:
        id = get_random_string(10, '0123456789')
        if not FiscalYear.objects.filter(fiscal_year_id=id).exists():
            return id
# Example: Fix for AutoIncrementCodeGenerator
class AutoIncrementCodeGenerator:
    def __init__(self, model, field, *, organization=None, prefix='', suffix='', padding=2):
        self.model = model
        self.field = field
        self.organization = organization
        self.prefix = prefix
        self.suffix = suffix
        self.padding = padding

    def generate_code(self):
        """Generate the next sequential code without scanning the target table."""
        from django.db import transaction

        model_label = self.model._meta.label_lower
        with transaction.atomic():
            sequence, _ = AutoIncrementSequence.objects.select_for_update().get_or_create(
                organization=self.organization,
                model_label=model_label,
                field_name=self.field,
                defaults={'next_value': 1},
            )

            next_value = sequence.next_value
            sequence.next_value = next_value + 1
            sequence.save(update_fields=['next_value'])

        number = str(next_value).zfill(self.padding)
        return f"{self.prefix}{number}{self.suffix}"


class AutoIncrementSequence(models.Model):
    """Persistence layer for AutoIncrementCodeGenerator using row-level locks."""

    sequence_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='auto_increment_sequences',
        null=True,
        blank=True,
    )
    model_label = models.CharField(max_length=255)
    field_name = models.CharField(max_length=255)
    next_value = models.BigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'auto_increment_sequence'
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'model_label', 'field_name'],
                name='unique_sequence_per_org_and_model_field',
            ),
            models.UniqueConstraint(
                fields=['model_label', 'field_name'],
                condition=Q(organization__isnull=True),
                name='unique_global_sequence_per_model_field',
            ),
        ]
        indexes = [
            models.Index(fields=['organization', 'model_label', 'field_name']),
        ]

    def __str__(self):
        org_part = self.organization.code if self.organization else 'global'
        return f"{org_part}::{self.model_label}.{self.field_name} -> {self.next_value}"
    
class FiscalYear(models.Model):
    """
    Represents a fiscal year for an organization.
    Defines the financial reporting period, status, and audit trail.
    Only one fiscal year per organization can be current at a time.
    """
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('archived', 'Archived'),
    ]
    id = models.CharField(default=get_random_string(10, '0123456789'), max_length=10, unique=True, editable=False)
    fiscal_year_id = models.CharField(max_length=10,primary_key=True, unique=True, default=generate_fiscal_year_id)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='fiscal_years',
    )
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    is_current = models.BooleanField(default=False)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='closed_fiscal_years')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_fiscal_years')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_fiscal_years')
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='archived_fiscal_years')
    is_default = models.BooleanField(default=False)
    rowversion = models.BinaryField(editable=False, null=True, blank=True, help_text="For MSSQL: ROWVERSION for optimistic concurrency.")

    class Meta:
        db_table = 'fiscal_years'
        ordering = ['-start_date']
        unique_together = ('organization', 'code')
        indexes = [
            models.Index(fields=['organization', 'is_current']),
            models.Index(fields=['organization', 'status']),
        ]
        constraints = [
            CheckConstraint(check=Q(start_date__lt=F('end_date')), name='fiscalyear_start_before_end'),
            UniqueConstraint(
                fields=['organization'],
                condition=Q(is_current=True),
                name='unique_current_fiscal_year_per_org',
            ),
            UniqueConstraint(
                fields=['organization'],
                condition=Q(is_default=True),
                name='unique_default_fiscal_year_per_org',
            ),
        ]
        # For DBA: Add UNIQUE WHERE is_current=1 and is_default=1 on (organization)
        # For DBA: CLUSTERED INDEX (organization, start_date)
        # For DBA: SYSTEM-VERSIONED TEMPORAL TABLE

    def __str__(self):
        return f"{self.code} - {self.name}"

    def clean(self):
        from django.core.exceptions import ValidationError
        # Validate date order
        if self.start_date >= self.end_date:
            raise ValidationError("Start date must be before end date.")

        # Only one is_current per org
        if self.is_current:
            qs = FiscalYear.objects.filter(organization_id=self.organization_id, is_current=True)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError("Only one fiscal year can be current per organization.")

        # Only one is_default per org
        if self.is_default:
            qs = FiscalYear.objects.filter(organization_id=self.organization_id, is_default=True)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError("Only one fiscal year can be default per organization.")

        # Prevent overlapping fiscal years for the same organization
        overlapping = FiscalYear.objects.filter(
            organization_id=self.organization_id,
            start_date__lte=self.end_date,
            end_date__gte=self.start_date,
        )
        if self.pk:
            overlapping = overlapping.exclude(pk=self.pk)
        if overlapping.exists():
            raise ValidationError("Fiscal year dates overlap with another fiscal year for this organization.")

   
        previous = (
            FiscalYear.objects.filter(
                organization_id=self.organization_id,
                end_date__lt=self.start_date,
            )
            .order_by('-end_date')
            .first()
        )
        if previous and (self.start_date - previous.end_date).days != 1:
            raise ValidationError(
                "Fiscal year must start the day after the previous fiscal year ends."
            )

        next_fy = (
            FiscalYear.objects.filter(
                organization_id=self.organization_id,
                start_date__gt=self.end_date,
            )
            .order_by('start_date')
            .first()
        )
        if next_fy and (next_fy.start_date - self.end_date).days != 1:
            raise ValidationError(
                "Fiscal year must end the day before the next fiscal year starts."
            )

    @classmethod
    def get_for_date(cls, organization, target_date):
        """Return the fiscal year covering the given date for an organization."""
        if organization is None:
            return None
        filters = {
            'organization': organization,
        }
        if target_date is not None:
            filters['start_date__lte'] = target_date
            filters['end_date__gte'] = target_date
            qs = cls.objects.filter(**filters)
        else:
            qs = cls.objects.filter(**filters)
        return qs.order_by('-is_current', '-start_date').first()
    def save(self, *args, **kwargs):
        logger.info(f"Saving FiscalYear: {self.code}")
        if not self.code:
            code_generator = AutoIncrementCodeGenerator(
                FiscalYear,
                'code',
                organization=self.organization,
                prefix='FY',
                suffix='',
            )
            self.code = code_generator.generate_code()
        # Enforce only one is_current per org
        if self.is_current:
            FiscalYear.objects.filter(organization_id=self.organization_id, is_current=True).exclude(pk=self.pk).update(is_current=False)
        # Enforce only one is_default per org
        if self.is_default:
            FiscalYear.objects.filter(organization_id=self.organization_id, is_default=True).exclude(pk=self.pk).update(is_default=False)
        self.full_clean()
        super(FiscalYear, self).save(*args, **kwargs)

        

class AccountingPeriod(models.Model):
    """
    Represents a period (month, quarter, etc.) within a fiscal year.
    Used for period-based reporting and posting control.
    """
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('adjustment', 'Adjustment'),
    ]

    period_id = models.BigAutoField(primary_key=True)
    fiscal_year = models.ForeignKey('FiscalYear', on_delete=models.PROTECT, related_name='periods')
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='accounting_periods',
        editable=False,
    )
    period_number = models.SmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(16)])
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    is_adjustment_period = models.BooleanField(default=False)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='closed_periods')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_periods')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_periods')
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    rowversion = models.BinaryField(editable=False, null=True, blank=True, help_text="For MSSQL: ROWVERSION for optimistic concurrency.")
    
    class Meta:
        unique_together = ('fiscal_year', 'period_number')
        ordering = ['fiscal_year', 'period_number']
        constraints = [
            CheckConstraint(check=Q(start_date__lt=F('end_date')), name='period_start_before_end'),
        ]
        # For DBA: UNIQUE (fiscal_year_id, period_number)
        # For DBA: FILTERED INDEX WHERE status='open'
        # For DBA: CHECK start/end inside parent FY
        # For DBA: ROWVERSION

    def __str__(self):
        return f"{self.fiscal_year.name} - {self.name}"

    def clean(self):
        from django.core.exceptions import ValidationError

        fy = None
        if self.fiscal_year_id:
            fy = self.fiscal_year
            if fy.organization_id is None:
                raise ValidationError("Fiscal year must belong to an organization before assigning a period.")
            # Keep organization in sync with fiscal year to avoid orphaned periods.
            self.organization_id = fy.organization_id

        if self.start_date >= self.end_date:
            raise ValidationError("Start date must be before end date.")

        # Ensure the period falls within its fiscal year
        if fy:
            if self.start_date < fy.start_date or self.end_date > fy.end_date:
                raise ValidationError(
                    "Period dates must be within the selected fiscal year."
                )

            overlapping = AccountingPeriod.objects.filter(
                fiscal_year=fy,
                start_date__lte=self.end_date,
                end_date__gte=self.start_date,
            )
            if self.pk:
                overlapping = overlapping.exclude(pk=self.pk)
            if overlapping.exists():
                raise ValidationError("Period dates overlap with an existing period.")

            if self.is_current:
                qs = AccountingPeriod.objects.filter(fiscal_year=fy, is_current=True)
                if self.pk:
                    qs = qs.exclude(pk=self.pk)
                if qs.exists():
                    raise ValidationError(
                        "Only one accounting period can be current per fiscal year."
                    )
    def save(self, *args, **kwargs):
        if self.fiscal_year_id:
            fy_org_id = self.fiscal_year.organization_id
            if fy_org_id is None:
                raise ValueError("Fiscal year must belong to an organization before saving periods.")
            self.organization_id = fy_org_id
        super().save(*args, **kwargs)

    @classmethod
    def is_date_in_open_period(cls, organization, date_to_check):
        """
        Checks if a given date is within any open accounting period for the organization.
        """
        return cls.objects.filter(
            organization=organization,
            start_date__lte=date_to_check,
            end_date__gte=date_to_check,
            status='open'
        ).exists()
    
    @classmethod
    def get_current_period(cls, organization):
        """Get the current accounting period for the organization."""
        from django.utils import timezone
        today = timezone.now().date()
        
        # Try to find an open period that contains today's date
        current_period = cls.objects.filter(
            organization=organization,
            start_date__lte=today,
            end_date__gte=today,
            status='open'
        ).first()
        
        if current_period:
            return current_period
        
        # Fallback: get the most recent open period
        fallback_period = cls.objects.filter(
            organization=organization,
            status='open'
        ).order_by('-end_date').first()
        
        return fallback_period

class Department(models.Model):
    department_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='departments',
        db_column='organization_id',
    )
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='archived_departments')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_departments')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_departments')
    rowversion = models.BinaryField(editable=False, null=True, blank=True, help_text="For MSSQL: ROWVERSION for optimistic concurrency.")

    class Meta:
        db_table = 'department'
        ordering = ['name']
        constraints = [
            CheckConstraint(check=Q(start_date__lt=F('end_date')), name='department_start_before_end'),
        ]
        # For DBA: NONCLUSTERED UNIQUE (organization_id, code)
        # For DBA: FILTERED INDEX WHERE is_active=1

    def __str__(self):
        # This will make Department objects display their name in dropdowns and elsewhere
        return self.name 

class Project(models.Model):
    project_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='projects', db_column='organization_id')
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_projects')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_projects')
    rowversion = models.BinaryField(editable=False, null=True, blank=True, help_text="For MSSQL: ROWVERSION for optimistic concurrency.")

    class Meta:
        db_table = 'project'
        ordering = ['name']
        constraints = [
            CheckConstraint(check=Q(start_date__lt=F('end_date')), name='project_start_before_end'),
        ]
        # For DBA: NONCLUSTERED UNIQUE (organization_id, code)
        # For DBA: FILTERED INDEX WHERE is_active=1
        
    def __str__(self):
        return f"{self.code} - {self.name}"
    def save(self, *args, **kwargs):
        if not self.code:
            code_generator = AutoIncrementCodeGenerator(
                Project,
                'code',
                organization=self.organization,
                prefix='PRJ',
                suffix='',
            )
            self.code = code_generator.generate_code()
        super(Project, self).save(*args, **kwargs)
class CostCenter(models.Model):
    cost_center_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='cost_centers', db_column='organization_id', null=True, blank=True)
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_cost_centers')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_cost_centers')
    rowversion = models.BinaryField(editable=False, null=True, blank=True, help_text="For MSSQL: ROWVERSION for optimistic concurrency.")

    class Meta:
        db_table = 'cost_center'
        ordering = ['name']
        constraints = [
            CheckConstraint(check=Q(start_date__lt=F('end_date')), name='costcenter_start_before_end'),
        ]
        # For DBA: NONCLUSTERED UNIQUE (organization_id, code)
        # For DBA: FILTERED INDEX WHERE is_active=1

    def __str__(self):
        return f"{self.code} - {self.name}"

class AccountType(models.Model):
    NATURE_CHOICES = [
        ('asset', 'Asset'),
        ('liability', 'Liability'),
        ('equity', 'Equity'),
        ('income', 'Income'),
        ('expense', 'Expense'),
    ]
    NATURE_CODE_PREFIX = {
        'asset': 'AST',
        'liability': 'LIA',
        'equity': 'EQT',
        'income': 'INC',
        'expense': 'EXP',
    }
    IFRS_DEFAULTS = {
        'asset': {
            'classification': 'Statement of Financial Position',
            'balance_sheet': 'Assets',
            'income_statement': None,
            'cash_flow': 'Investing Activities',
        },
        'liability': {
            'classification': 'Statement of Financial Position',
            'balance_sheet': 'Liabilities',
            'income_statement': None,
            'cash_flow': 'Financing Activities',
        },
        'equity': {
            'classification': 'Statement of Financial Position',
            'balance_sheet': 'Equity',
            'income_statement': None,
            'cash_flow': 'Financing Activities',
        },
        'income': {
            'classification': 'Statement of Profit or Loss',
            'balance_sheet': None,
            'income_statement': 'Revenue',
            'cash_flow': 'Operating Activities',
        },
        'expense': {
            'classification': 'Statement of Profit or Loss',
            'balance_sheet': None,
            'income_statement': 'Expense',
            'cash_flow': 'Operating Activities',
        },
    }
    account_type_id = models.BigAutoField(primary_key=True)
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    nature = models.CharField(max_length=10, choices=NATURE_CHOICES)
    classification = models.CharField(max_length=50)
    balance_sheet_category = models.CharField(max_length=50, null=True, blank=True)
    income_statement_category = models.CharField(max_length=50, null=True, blank=True)
    cash_flow_category = models.CharField(max_length=50, null=True, blank=True)
    system_type = models.BooleanField(default=True)
    display_order = models.BigIntegerField()
    root_code_prefix = models.CharField(max_length=10, null=True, blank=True,
                                        help_text="Starting prefix for top level account codes")
    root_code_step = models.BigIntegerField(default=100,
                                                help_text="Increment step for generating top level codes")
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='archived_account_types')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_account_types')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_account_types')
    rowversion = models.BinaryField(editable=False, null=True, blank=True, help_text="For MSSQL: ROWVERSION for optimistic concurrency.")
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    def save(self, *args, **kwargs):
        if not self.root_code_prefix:
            self.root_code_prefix = {
                'asset': '1000',
                'liability': '2000',
                'equity': '3000',
                'income': '4000',
                'expense': '5000',
            }.get(self.nature, '9000')
        if not self.root_code_step:
            self.root_code_step = 100
        defaults = self.IFRS_DEFAULTS.get(self.nature, {})
        if not self.classification and defaults.get('classification'):
            self.classification = defaults['classification']
        if not self.balance_sheet_category and defaults.get('balance_sheet'):
            self.balance_sheet_category = defaults['balance_sheet']
        if not self.income_statement_category and defaults.get('income_statement'):
            self.income_statement_category = defaults['income_statement']
        if not self.cash_flow_category and defaults.get('cash_flow'):
            self.cash_flow_category = defaults['cash_flow']
        if not self.code:
            prefix = self.NATURE_CODE_PREFIX.get(self.nature, 'ACC')
            # Get max code with the same prefix
            max_code = (
                AccountType.objects
                .filter(code__startswith=prefix)
                .aggregate(Max('code'))
                .get('code__max')
            )

            if max_code:
                try:
                    last_num = int(max_code.replace(prefix, ''))
                except ValueError:
                    last_num = 0
            else:
                last_num = 0

            next_num = last_num + 1
            self.code = f"{prefix}{next_num:03d}"  # e.g., AST001

        super(AccountType, self).save(*args, **kwargs)

    class Meta:
        db_table = 'account_type'
        ordering = ['name']
        constraints = [
            CheckConstraint(check=Q(root_code_step__gt=0), name='accounttype_root_code_step_positive'),
        ]
        # For DBA: PAGE compression, mark as static reference

class Currency(models.Model):
    currency_code = models.CharField(max_length=3, primary_key=True)
    currency_name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=10)
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_currencies')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_currencies')
    rowversion = models.BinaryField(editable=False, null=True, blank=True, help_text="For MSSQL: ROWVERSION for optimistic concurrency.")
    archived_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='archived_currencies')

    class Meta:
        db_table = 'currency'
        verbose_name_plural = "Currencies"
        ordering = ['currency_code']

    def __str__(self):
        return f"{self.currency_code} - {self.currency_name}"


code_validator = RegexValidator(r'^\d{4}(?:\.\d{2})*$', 'Invalid COA code format.')

MAX_COA_DEPTH = getattr(settings, 'COA_MAX_DEPTH', 10)
MAX_COA_SIBLINGS = getattr(settings, 'COA_MAX_SIBLINGS', 99)


class ActiveAccountManager(models.Manager):
    """Manager that returns only non-archived accounts."""

    def get_queryset(self):
        return super().get_queryset().filter(archived_at__isnull=True)


class ChartOfAccount(models.Model):
    # Default starting codes for each account nature. New top level accounts are
    # created using these prefixes and incremented in steps of ``100``.
    # The values also determine the length used when zero padding generated codes.
    NATURE_ROOT_CODE = {
        'asset': '1000',
        'liability': '2000',
        'equity': '3000',
        'income': '4000',
        'expense': '5000',
    }
    ROOT_STEP = 100
    account_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='chart_of_accounts',
        db_column='organization_id',
    )
    parent_account = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)
    account_type = models.ForeignKey(AccountType, on_delete=models.PROTECT, db_column='account_type_id')
    account_code = models.CharField(max_length=50, validators=[code_validator])
    account_name = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    is_bank_account = models.BooleanField(default=False)
    # Allow users to override the auto-generated code if needed
    use_custom_code = models.BooleanField(default=False)
    custom_code = models.CharField(max_length=50, null=True, blank=True, validators=[code_validator])
    bank_name = models.CharField(max_length=100, null=True, blank=True)
    bank_branch = models.CharField(max_length=100, null=True, blank=True)
    account_number = models.CharField(max_length=64, null=True, blank=True)
    swift_code = models.CharField(
        max_length=11,
        null=True,
        blank=True,
        help_text="SWIFT/BIC code (8 or 11 characters)"
    )
    is_control_account = models.BooleanField(default=False)
    control_account_type = models.CharField(max_length=50, null=True, blank=True)
    require_cost_center = models.BooleanField(default=False)
    require_project = models.BooleanField(default=False)
    require_department = models.BooleanField(default=False)
    default_tax_code = models.CharField(max_length=50, null=True, blank=True)
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE, null=True, blank=True, related_name='accounts', db_column='currency_id')
    opening_balance = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    current_balance = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    reconciled_balance = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    last_reconciled_date = models.DateTimeField(null=True, blank=True)
    allow_manual_journal = models.BooleanField(default=True)
    account_level = models.SmallIntegerField(default=1)
    tree_path = models.CharField(max_length=255, null=True, blank=True)
    display_order = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_accounts')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_accounts')
    rowversion = models.BinaryField(editable=False, null=True, blank=True, help_text="For MSSQL: ROWVERSION for optimistic concurrency.")
    archived_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='archived_accounts')

    objects = models.Manager()
    active_accounts = ActiveAccountManager()
    
    class Meta:
        db_table = 'chart_of_account'
        unique_together = ('organization', 'account_code')
        ordering = ['account_code']
        indexes = [
            models.Index(fields=['parent_account']),
            models.Index(fields=['account_type']),
            models.Index(fields=['is_active']),
            models.Index(fields=['tree_path']),
        ]
        # For DBA: Clustered on (organization_id, account_code); non-clustered on parent_account
        # For DBA: tree_path as persisted hierarchyid
        # For DBA: PAGE compression

    def __str__(self):
        return f"{self.account_code} - {self.account_name}"

    def total_balance(self):
        """Return current balance including balances of all child accounts."""
        total = self.current_balance
        for child in ChartOfAccount.objects.filter(parent_account=self):
            total += child.total_balance()
        return total

    # Backwards-compatibility aliases for legacy 'Account' API
    @property
    def code(self):
        return self.account_code

    @property
    def name(self):
        return self.account_name

    @property
    def balance(self):
        return self.current_balance

    def clean(self):
        # Circular reference check
        if self.parent_account:
            ancestor = self.parent_account
            depth = 1
            while ancestor:
                if ancestor == self:
                    raise ValidationError("Circular parent relationship detected.")
                ancestor = ancestor.parent_account
                depth += 1
                if depth > MAX_COA_DEPTH:
                    raise ValidationError(
                        f"Account tree is too deep (max {MAX_COA_DEPTH} levels)."
                    )
        # Suffix overflow check for children
        org_id = getattr(self, 'organization_id', None) or (self.organization.pk if hasattr(self, 'organization') and self.organization else None)
        if self.parent_account:
            if not org_id:
                raise ValidationError("Organization must be set before validating child accounts.")
            siblings = ChartOfAccount.objects.filter(parent_account=self.parent_account, organization_id=org_id)
            
            if siblings.count() >= MAX_COA_SIBLINGS:
                raise ValidationError(
                    f"Maximum number of child accounts ({MAX_COA_SIBLINGS}) reached for this parent."
                )
        super().clean()
        # Custom code validation and uniqueness per organization
        if self.use_custom_code:
            if not self.custom_code:
                raise ValidationError("Custom code is required when 'Use Custom Code' is enabled.")
            # Ensure format is valid
            import re as _re
            if not _re.match(r'^[0-9]+(\.[0-9]{2})*$', self.custom_code):
                raise ValidationError("Custom code format is invalid.")
            # Unique within organization
            qs = ChartOfAccount.objects.filter(organization_id=self.organization_id, account_code=self.custom_code)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError("Another account with the same custom code exists in this organization.")
    def save(self, *args, **kwargs):
        with transaction.atomic():
            logger.debug(f"ChartOfAccount.save: Called for pk={self.pk}, account_code={self.account_code}")
            # Apply custom code override
            if self.use_custom_code and self.custom_code:
                self.account_code = self.custom_code
            if not self.account_code:
                logger.debug("ChartOfAccount.save: Generating account_code...")
                if self.parent_account:
                    siblings = ChartOfAccount.objects.filter(
                        parent_account=self.parent_account,
                        organization=self.organization,
                    )
                    sibling_codes = siblings.values_list('account_code', flat=True)
                    base_code = self.parent_account.account_code
                    used_suffixes = set()
                    for code in sibling_codes:
                        if code.startswith(base_code + "."):
                            try:
                                suffix = int(code.replace(base_code + ".", ""))
                                used_suffixes.add(suffix)
                            except ValueError:
                                continue
                    # Find the first unused suffix within the configured limit
                    next_suffix = None
                    for i in range(1, MAX_COA_SIBLINGS + 1):
                        if i not in used_suffixes:
                            next_suffix = i
                            break
                    if next_suffix is None:
                        raise ValidationError(
                            f"Maximum number of child accounts ({MAX_COA_SIBLINGS}) reached for this parent."
                        )
                    self.account_code = f"{base_code}.{next_suffix:02d}"
                    logger.debug(f"ChartOfAccount.save: Generated child account_code={self.account_code}")
                else:
                    root_code = self.account_type and self.account_type.nature
                    root_prefix = (
                        self.account_type.root_code_prefix
                        or self.NATURE_ROOT_CODE.get(root_code, '9000')
                    )
                    step = self.account_type.root_code_step or self.ROOT_STEP
                    top_levels = ChartOfAccount.objects.filter(
                        parent_account__isnull=True,
                        organization=self.organization,
                        account_code__startswith=root_prefix
                    )
                    used_codes = set()
                    for acc in top_levels:
                        try:
                            acc_num = int(acc.account_code)
                            if str(acc_num).startswith(root_prefix):
                                used_codes.add(acc_num)
                        except ValueError:
                            continue
                    # Find the first unused code in the sequence
                    start_code = int(root_prefix)
                    next_code = None
                    for i in range(start_code, start_code + step * MAX_COA_SIBLINGS, step):
                        if i not in used_codes:
                            next_code = i
                            break
                    if next_code is None:
                        raise ValidationError(
                            f"Maximum number of top-level accounts ({MAX_COA_SIBLINGS}) reached for this type."
                        )
                    self.account_code = str(next_code).zfill(len(root_prefix))
                    logger.debug(f"ChartOfAccount.save: Generated top-level account_code={self.account_code}")
            if self.parent_account:
                self.tree_path = f"{self.parent_account.tree_path}/{self.account_code}" if self.parent_account.tree_path else self.account_code
            else:
                self.tree_path = self.account_code
            self.full_clean()
            logger.debug(f"ChartOfAccount.save: Saving with account_code={self.account_code}")
            super(ChartOfAccount, self).save(*args, **kwargs)


class AccountingSettings(models.Model):
    """Organization-level accounting settings for statutory controls."""

    IFRS = 'ifrs'
    NFRS = 'nfrs'
    GAAP = 'gaap'

    REPORTING_FRAMEWORK_CHOICES = [
        (IFRS, 'IFRS'),
        (NFRS, 'NFRS'),
        (GAAP, 'GAAP / Local GAAP'),
    ]

    settings_id = models.BigAutoField(primary_key=True)
    organization = models.OneToOneField(
        Organization,
        on_delete=models.CASCADE,
        related_name='accounting_settings',
    )
    retained_earnings_account = models.ForeignKey(
        'ChartOfAccount',
        on_delete=models.PROTECT,
        related_name='+',
    )
    current_year_income_account = models.ForeignKey(
        'ChartOfAccount',
        on_delete=models.PROTECT,
        related_name='+',
    )
    statutory_framework = models.CharField(
        max_length=16,
        choices=REPORTING_FRAMEWORK_CHOICES,
        default=IFRS,
        help_text='Primary statutory reporting framework used for classifications.',
    )
    auto_rollover_closing = models.BooleanField(
        default=False,
        help_text='Automatically generate opening balance journals after fiscal year close.',
    )
    auto_fx_lookup = models.BooleanField(
        default=True,
        help_text='Automatically hydrate exchange rates from CurrencyExchangeRate records when posting.',
    )
    enable_currency_revaluation = models.BooleanField(
        default=False,
        help_text='Run currency revaluation jobs during fiscal close.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'accounting_settings'
        verbose_name_plural = 'Accounting Settings'

    def __str__(self):
        return f"Accounting settings for {self.organization.name}"


class JournalDebugPreference(models.Model):
    """Per-organization switch that exposes the UI debug panel safely."""

    organization = models.OneToOneField(
        Organization,
        on_delete=models.CASCADE,
        related_name="journal_debug_preference",
    )
    enabled = models.BooleanField(
        default=False,
        help_text="When enabled, voucher entry surfaces an in-page debug panel for save flows.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="journal_debug_preferences",
        help_text="Tracks who last toggled the debug mode.",
    )

    class Meta:
        db_table = "journal_debug_preferences"
        verbose_name = "Journal Debug Preference"
        verbose_name_plural = "Journal Debug Preferences"

    def __str__(self):
        status = "enabled" if self.enabled else "disabled"
        return f"Journal debug {status} for {self.organization.name}"

    @classmethod
    def is_enabled_for(cls, organization):
        if not organization:
            return False
        return cls.objects.filter(organization=organization, enabled=True).exists()


class PaymentTerm(models.Model):
    """Stores payables/receivables payment terms per organization."""

    TERM_TYPE_CHOICES = [
        ('ap', 'Accounts Payable'),
        ('ar', 'Accounts Receivable'),
        ('both', 'Both'),
    ]

    payment_term_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='payment_terms',
    )
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    term_type = models.CharField(
        max_length=10,
        choices=TERM_TYPE_CHOICES,
        default='both',
    )
    description = models.TextField(blank=True)
    net_due_days = models.PositiveIntegerField(
        default=30,
        validators=[MinValueValidator(0), MaxValueValidator(365)],
        help_text='Number of days from invoice date to calculate the due date.',
    )
    discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text='Early-payment discount percentage (e.g. 2.00 for 2%).',
    )
    discount_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Number of days to qualify for the discount.',
    )
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_payment_terms',
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_payment_terms',
    )

    class Meta:
        db_table = 'payment_term'
        unique_together = ('organization', 'code')
        ordering = ('name',)

    def __str__(self):
        return f"{self.code} - {self.name}"

    def calculate_due_date(self, reference_date):
        if reference_date is None:
            raise ValueError("reference_date is required to calculate due date.")
        return reference_date + timedelta(days=self.net_due_days)

    def calculate_discount_due_date(self, reference_date):
        if (
            reference_date is None
            or self.discount_percent <= 0
            or not self.discount_days
        ):
            return None
        return reference_date + timedelta(days=self.discount_days)


class Vendor(models.Model):
    """Vendor master record with payment defaults."""

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('on_hold', 'On Hold'),
        ('inactive', 'Inactive'),
    ]

    vendor_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='vendors',
    )
    code = models.CharField(max_length=30)
    display_name = models.CharField(max_length=255)
    legal_name = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    tax_id = models.CharField(max_length=50, blank=True)
    payment_term = models.ForeignKey(
        PaymentTerm,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'term_type__in': ['ap', 'both']},
    )
    default_currency = models.ForeignKey(
        'Currency',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='vendor_currency',
    )
    accounts_payable_account = models.ForeignKey(
        'ChartOfAccount',
        on_delete=models.PROTECT,
        related_name='vendors_ap_account',
    )
    expense_account = models.ForeignKey(
        'ChartOfAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vendors_expense_account',
    )
    email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=50, blank=True)
    website = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    credit_limit = models.DecimalField(max_digits=19, decimal_places=4, null=True, blank=True)
    on_hold = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_vendors',
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_vendors',
    )

    class Meta:
        db_table = 'vendor'
        unique_together = ('organization', 'code')
        ordering = ('display_name',)

    def __str__(self):
        return f"{self.code} - {self.display_name}"

    def primary_address(self):
        return self.addresses.filter(is_primary=True).first() or self.addresses.first()

    def primary_contact(self):
        return self.contacts.filter(is_primary=True).first() or self.contacts.first()

    def remit_address(self):
        """Return the remit address if present, otherwise fall back to the primary address."""
        return self.addresses.filter(address_type='remit').first() or self.primary_address()


class VendorAddress(models.Model):
    """Vendor address book entries."""

    ADDRESS_CHOICES = [
        ('billing', 'Billing'),
        ('shipping', 'Shipping'),
        ('remit', 'Remittance'),
        ('other', 'Other'),
    ]

    address_id = models.BigAutoField(primary_key=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='addresses')
    address_type = models.CharField(max_length=20, choices=ADDRESS_CHOICES, default='billing')
    line1 = models.CharField(max_length=255)
    line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state_province = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country_code = models.CharField(max_length=2, default='US')
    is_primary = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'vendor_address'
        indexes = [
            models.Index(fields=['vendor', 'address_type']),
        ]

    def __str__(self):
        return f"{self.vendor.display_name} - {self.address_type}"


class VendorContact(models.Model):
    """Vendor contacts (AP, sales reps, etc.)."""

    contact_id = models.BigAutoField(primary_key=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='contacts')
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    mobile = models.CharField(max_length=50, blank=True)
    job_title = models.CharField(max_length=100, blank=True)
    is_primary = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'vendor_contact'
        indexes = [
            models.Index(fields=['vendor', 'is_primary']),
        ]

    def __str__(self):
        return f"{self.name} ({self.vendor.display_name})"


class VendorBankAccount(models.Model):
    """Banking instructions per vendor for payments."""

    bank_account_id = models.BigAutoField(primary_key=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='bank_accounts')
    bank_name = models.CharField(max_length=255)
    account_name = models.CharField(max_length=255)
    account_number = models.CharField(max_length=50)
    routing_number = models.CharField(max_length=50, blank=True)
    swift_code = models.CharField(max_length=20, blank=True)
    iban = models.CharField(max_length=34, blank=True)
    currency = models.ForeignKey(
        'Currency',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vendor_bank_currency',
    )
    is_primary = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'vendor_bank_account'
        indexes = [
            models.Index(fields=['vendor', 'is_primary']),
        ]

    def __str__(self):
        return f"{self.bank_name} - {self.account_number}"


class PurchaseInvoice(models.Model):
    """Vendor invoice header supporting 3-way match and posting."""

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('validated', 'Validated'),
        ('matched', 'Matched'),
        ('ready_for_posting', 'Ready for Posting'),
        ('posted', 'Posted'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ]
    MATCH_STATUS_CHOICES = [
        ('not_required', 'Not Required'),
        ('pending', 'Pending'),
        ('matched', 'Matched'),
        ('variance', 'Variance'),
        ('rejected', 'Rejected'),
    ]

    invoice_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='purchase_invoices',
    )
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.PROTECT,
        related_name='purchase_invoices',
    )
    vendor_display_name = models.CharField(max_length=255)
    invoice_number = models.CharField(max_length=50, blank=True, default='')
    external_reference = models.CharField(max_length=100, blank=True)
    invoice_date = models.DateField()
    due_date = models.DateField()
    payment_term = models.ForeignKey(
        PaymentTerm,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    currency = models.ForeignKey(
        'Currency',
        on_delete=models.PROTECT,
        related_name='purchase_invoice_currency',
    )
    exchange_rate = models.DecimalField(max_digits=19, decimal_places=6, default=1)
    subtotal = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    tax_total = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    total = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    base_currency_total = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='draft')
    match_status = models.CharField(
        max_length=20,
        choices=MATCH_STATUS_CHOICES,
        default='not_required',
    )
    po_number = models.CharField(max_length=50, blank=True)
    receipt_reference = models.CharField(max_length=50, blank=True)
    match_summary = models.JSONField(default=list, blank=True)
    journal = models.ForeignKey(
        'Journal',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchase_invoices',
    )
    metadata = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_purchase_invoices',
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_purchase_invoices',
    )

    class Meta:
        db_table = 'purchase_invoice'
        unique_together = ('organization', 'invoice_number')
        ordering = ('-invoice_date', '-invoice_id')
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['organization', 'match_status']),
        ]

    def __str__(self):
        return f"{self.invoice_number} - {self.vendor_display_name}"

    def recompute_totals(self, save=True):
        aggregates = self.lines.aggregate(
            subtotal=Sum('line_total'),
            tax_total=Sum('tax_amount'),
        )
        subtotal = aggregates.get('subtotal') or Decimal('0')
        tax_total = aggregates.get('tax_total') or Decimal('0')
        self.subtotal = subtotal
        self.tax_total = tax_total
        self.total = subtotal + tax_total
        self.base_currency_total = (self.total or Decimal('0')) * (self.exchange_rate or Decimal('1'))
        if save:
            super().save(update_fields=['subtotal', 'tax_total', 'total', 'base_currency_total', 'updated_at'])

    def clean(self):
        super().clean()
        if not self.pk:
            return
        original = PurchaseInvoice.objects.get(pk=self.pk)
        if original.status == 'posted' and original.invoice_number != self.invoice_number:
            raise ValidationError("Invoice number cannot be changed after posting.")

    def save(self, *args, **kwargs):
        if not self.invoice_number and self.organization_id:
            document_date = self.invoice_date or timezone.now().date()
            self.invoice_number = DocumentSequenceConfig.get_next_number(
                organization=self.organization,
                document_type='purchase_invoice',
                document_date=document_date,
            )
        super().save(*args, **kwargs)


class PurchaseInvoiceLine(models.Model):
    """Line detail capturing quantity/cost/tax."""

    invoice_line_id = models.BigAutoField(primary_key=True)
    invoice = models.ForeignKey(
        PurchaseInvoice,
        on_delete=models.CASCADE,
        related_name='lines',
    )
    line_number = models.PositiveIntegerField()
    description = models.TextField()
    product_code = models.CharField(max_length=100, blank=True)
    quantity = models.DecimalField(max_digits=19, decimal_places=4, default=1)
    unit_cost = models.DecimalField(max_digits=19, decimal_places=6, default=0)
    discount_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    line_total = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    account = models.ForeignKey(
        ChartOfAccount,
        on_delete=models.PROTECT,
        related_name='purchase_invoice_lines',
    )
    tax_code = models.ForeignKey(
        'TaxCode',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchase_invoice_lines',
    )
    tax_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    cost_center = models.ForeignKey(
        'CostCenter',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    department = models.ForeignKey(
        'Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    project = models.ForeignKey(
        'Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    dimension_value = models.ForeignKey(
        'DimensionValue',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchase_invoice_lines',
    )
    po_reference = models.CharField(max_length=100, blank=True)
    receipt_reference = models.CharField(max_length=100, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'purchase_invoice_line'
        unique_together = ('invoice', 'line_number')
        ordering = ('invoice', 'line_number')

    def __str__(self):
        return f"{self.invoice.invoice_number} - line {self.line_number}"

    def clean(self):
        if self.quantity <= 0:
            raise ValidationError("Quantity must be greater than zero.")
        if self.unit_cost < 0:
            raise ValidationError("Unit cost cannot be negative.")
        super().clean()

    def save(self, *args, **kwargs):
        self.line_total = (self.quantity * self.unit_cost) - (self.discount_amount or Decimal('0'))
        super().save(*args, **kwargs)


class PurchaseInvoiceMatch(models.Model):
    """Stores the outcome of comparing invoice lines vs. PO and receipt data."""

    MATCH_RESULT_CHOICES = [
        ('matched', 'Matched'),
        ('over_receipt', 'Over Receipt'),
        ('short_receipt', 'Short Receipt'),
        ('price_variance', 'Price Variance'),
        ('pending', 'Pending'),
    ]

    match_id = models.BigAutoField(primary_key=True)
    invoice = models.ForeignKey(
        PurchaseInvoice,
        on_delete=models.CASCADE,
        related_name='match_results',
    )
    invoice_line = models.ForeignKey(
        PurchaseInvoiceLine,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='match_results',
    )
    po_reference = models.CharField(max_length=100, blank=True)
    receipt_reference = models.CharField(max_length=100, blank=True)
    expected_quantity = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    received_quantity = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    invoiced_quantity = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    unit_price_variance = models.DecimalField(max_digits=19, decimal_places=6, default=0)
    status = models.CharField(max_length=20, choices=MATCH_RESULT_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_purchase_invoice_matches',
    )

    class Meta:
        db_table = 'purchase_invoice_match'
        ordering = ('invoice', 'match_id')
        indexes = [
            models.Index(fields=['invoice', 'status']),
        ]

    def __str__(self):
        return f"Match result for {self.invoice.invoice_number}"


class BankAccount(models.Model):
    """Captures bank account master data for cash/bank management."""

    ACCOUNT_TYPE_CHOICES = [
        ('checking', 'Checking'),
        ('savings', 'Savings'),
        ('credit', 'Credit'),
    ]

    account_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='bank_accounts',
    )
    bank_name = models.CharField(max_length=200)
    account_name = models.CharField(max_length=200)
    account_number = models.CharField(max_length=64)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES, default='checking')
    currency = models.ForeignKey('Currency', on_delete=models.PROTECT)
    routing_number = models.CharField(max_length=50, blank=True)
    swift_code = models.CharField(max_length=20, blank=True)
    opening_balance = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    current_balance = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    last_reconciled_on = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bank_account'
        unique_together = ('organization', 'account_number')
        ordering = ('bank_name', 'account_name')

    def __str__(self):
        return f"{self.bank_name}/{self.account_number}"


class CashAccount(models.Model):
    """Defines cash petty cash accounts."""

    account_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='cash_accounts',
    )
    name = models.CharField(max_length=200)
    currency = models.ForeignKey('Currency', on_delete=models.PROTECT)
    current_balance = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    location = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'cash_account'
        ordering = ('name',)

    def __str__(self):
        return self.name


class BankTransaction(models.Model):
    """Ledger entries imported or created for reconciliation."""

    TRANSACTION_TYPE_CHOICES = [
        ('receipt', 'Receipt'),
        ('payment', 'Payment'),
        ('transfer', 'Transfer'),
    ]

    transaction_id = models.BigAutoField(primary_key=True)
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.CASCADE,
        related_name='transactions',
    )
    transaction_date = models.DateField()
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    reference = models.CharField(max_length=100, blank=True)
    description = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=19, decimal_places=4)
    is_reconciled = models.BooleanField(default=False)
    reconciled_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'bank_transaction'
        ordering = ('-transaction_date',)

    def __str__(self):
        return f"{self.bank_account.account_number} {self.reference} {self.amount}"


class BankStatement(models.Model):
    """Imported bank statement with line items."""

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('matched', 'Matched'),
        ('closed', 'Closed'),
    ]

    statement_id = models.BigAutoField(primary_key=True)
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.CASCADE,
        related_name='statements',
    )
    period_start = models.DateField()
    period_end = models.DateField()
    imported_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'bank_statement'
        ordering = ('-period_start',)

    def __str__(self):
        return f"{self.bank_account.account_number} {self.period_start} - {self.period_end}"


class BankStatementLine(models.Model):
    """Individual statement entries for reconciliation."""

    statement_line_id = models.BigAutoField(primary_key=True)
    statement = models.ForeignKey(
        BankStatement,
        on_delete=models.CASCADE,
        related_name='lines',
    )
    line_date = models.DateField()
    description = models.CharField(max_length=255)
    reference = models.CharField(max_length=100, blank=True)
    amount = models.DecimalField(max_digits=19, decimal_places=4)
    matched_transaction = models.ForeignKey(
        BankTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='statement_lines',
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'bank_statement_line'
        ordering = ('line_date',)

    def __str__(self):
        return f"{self.line_date} {self.amount}"


class Budget(models.Model):
    """Captures approved budgets per organization, fiscal year, and version."""

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('in_review', 'In Review'),
        ('approved', 'Approved'),
        ('archived', 'Archived'),
    ]

    budget_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='budgets',
    )
    name = models.CharField(max_length=255)
    fiscal_year = models.ForeignKey(
        'FiscalYear',
        on_delete=models.PROTECT,
        related_name='budgets',
    )
    version = models.CharField(max_length=50, default='01')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    metadata = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'budget'
        unique_together = ('organization', 'fiscal_year', 'version')
        ordering = ('-fiscal_year', 'name')

    def __str__(self):
        return f"{self.fiscal_year.code} - {self.name} v{self.version}"


class BudgetLine(models.Model):
    """Detail rows for budgeting specific accounts/dimensions."""

    budget_line_id = models.BigAutoField(primary_key=True)
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name='lines')
    account = models.ForeignKey(ChartOfAccount, on_delete=models.PROTECT)
    amount_by_month = models.JSONField(default=dict, blank=True, help_text="Amount per period (keyed by 1..12)")
    total_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    dimension_value = models.ForeignKey(
        'DimensionValue',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    project = models.ForeignKey(
        'Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    cost_center = models.ForeignKey(
        'CostCenter',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    department = models.ForeignKey(
        'Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'budget_line'
        unique_together = ('budget', 'account', 'dimension_value', 'project', 'cost_center', 'department')

    def clean(self):
        if not self.amount_by_month:
            raise ValidationError("Amount per month cannot be empty.")
        super().clean()

    def save(self, *args, **kwargs):
        self.total_amount = sum(Decimal(str(v)) for v in self.amount_by_month.values())
        super().save(*args, **kwargs)


class AssetCategory(models.Model):
    """Classifies assets for depreciation policies."""

    category_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='asset_categories',
    )
    name = models.CharField(max_length=200)
    depreciation_expense_account = models.ForeignKey(
        ChartOfAccount,
        on_delete=models.PROTECT,
        related_name='category_expense_account',
    )
    accumulated_depreciation_account = models.ForeignKey(
        ChartOfAccount,
        on_delete=models.PROTECT,
        related_name='category_accumulated_account',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'asset_category'
        unique_together = ('organization', 'name')
        ordering = ('name',)

    def __str__(self):
        return f"{self.organization.code} - {self.name}"


class Asset(models.Model):
    """Represents a fixed asset with depreciation metadata."""

    METHOD_CHOICES = [
        ('straight_line', 'Straight Line'),
        ('declining_balance', 'Declining Balance'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('disposed', 'Disposed'),
    ]

    asset_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='assets',
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.ForeignKey(AssetCategory, on_delete=models.PROTECT, related_name='assets')
    acquisition_date = models.DateField()
    cost = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    salvage_value = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    useful_life_years = models.DecimalField(max_digits=5, decimal_places=2, default=1)
    depreciation_method = models.CharField(max_length=32, choices=METHOD_CHOICES, default='straight_line')
    accumulated_depreciation = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    disposed_at = models.DateField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'asset'
        ordering = ('name',)

    def __str__(self):
        return self.name

    @property
    def book_value(self):
        return max(self.cost - self.accumulated_depreciation, Decimal('0'))


class AssetEvent(models.Model):
    """Captures events like disposal or transfer affecting an asset."""

    EVENT_CHOICES = [
        ('disposal', 'Disposal'),
        ('impairment', 'Impairment'),
        ('revaluation', 'Revaluation'),
    ]

    event_id = models.BigAutoField(primary_key=True)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='events')
    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES)
    event_date = models.DateField()
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'asset_event'
        ordering = ('-event_date',)

    def __str__(self):
        return f"{self.asset.name} {self.event_type} on {self.event_date}"


class IntegrationEvent(models.Model):
    """Stores webhook-ready events emitted by accounting objects."""

    event_id = models.BigAutoField(primary_key=True)
    event_type = models.CharField(max_length=100)
    payload = models.JSONField()
    source_object = models.CharField(max_length=255)
    source_id = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'integration_event'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.event_type} for {self.source_object} {self.source_id}"


class ApprovalWorkflow(models.Model):
    """Configures sequential approval steps for journals/payments."""

    AREA_CHOICES = [
        ('journal', 'Journal'),
        ('payment', 'Payment'),
    ]

    workflow_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='approval_workflows',
    )
    name = models.CharField(max_length=200)
    area = models.CharField(max_length=20, choices=AREA_CHOICES)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'approval_workflow'
        unique_together = ('organization', 'name', 'area')
        ordering = ('organization', 'name')

    def __str__(self):
        return f"{self.organization.code} / {self.name} ({self.area})"


class ApprovalStep(models.Model):
    """Defines each sequential approver requirement."""

    step_id = models.BigAutoField(primary_key=True)
    workflow = models.ForeignKey(ApprovalWorkflow, on_delete=models.CASCADE, related_name='steps')
    sequence = models.PositiveIntegerField()
    role = models.CharField(max_length=100)
    min_amount = models.DecimalField(max_digits=19, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'approval_step'
        ordering = ('workflow', 'sequence')
        unique_together = ('workflow', 'sequence')

    def __str__(self):
        return f"{self.workflow.name} step {self.sequence} ({self.role})"


class ApprovalTask(models.Model):
    """Records approval status for journal/payment submissions."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]

    task_id = models.BigAutoField(primary_key=True)
    workflow = models.ForeignKey(
        ApprovalWorkflow,
        on_delete=models.PROTECT,
        related_name='tasks',
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    current_step = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    initiator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'approval_task'
        ordering = ('-updated_at',)

    def __str__(self):
        return f"{self.workflow.name} task for {self.content_object}"
class TaxLiability(models.Model):
    """Tracks periodic tax liabilities per tax code."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('reported', 'Reported'),
        ('paid', 'Paid'),
    ]

    liability_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='tax_liabilities',
    )
    tax_code = models.ForeignKey(
        'TaxCode',
        on_delete=models.PROTECT,
        related_name='liabilities',
    )
    period_start = models.DateField()
    period_end = models.DateField()
    amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reported_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'tax_liability'
        ordering = ('-period_end',)
        unique_together = ('organization', 'tax_code', 'period_start', 'period_end')

    def __str__(self):
        return f"{self.tax_code.code} {self.period_start} - {self.period_end}"


class PaymentBatch(models.Model):
    """Groups vendor payments for scheduling/approval."""

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('approved', 'Approved'),
        ('processed', 'Processed'),
        ('cancelled', 'Cancelled'),
    ]

    batch_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='payment_batches',
    )
    batch_number = models.CharField(max_length=30)
    scheduled_date = models.DateField()
    currency = models.ForeignKey('Currency', on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    total_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_payment_batches',
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_payment_batches',
    )

    class Meta:
        db_table = 'payment_batch'
        unique_together = ('organization', 'batch_number')
        ordering = ('-scheduled_date', '-batch_id')

    def __str__(self):
        return f"{self.batch_number} ({self.status})"

    def recompute_total(self):
        aggregates = self.payments.aggregate(total=Sum('amount'))
        self.total_amount = aggregates.get('total') or Decimal('0')
        self.save(update_fields=['total_amount', 'updated_at'])


class APPayment(models.Model):
    """Represents an outbound vendor payment."""

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('executed', 'Executed'),
        ('reconciled', 'Reconciled'),
        ('cancelled', 'Cancelled'),
    ]

    payment_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='ap_payments',
    )
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.PROTECT,
        related_name='payments',
    )
    payment_number = models.CharField(max_length=30)
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=50, default='bank_transfer')
    bank_account = models.ForeignKey(
        ChartOfAccount,
        on_delete=models.PROTECT,
        related_name='ap_bank_payments',
    )
    currency = models.ForeignKey('Currency', on_delete=models.PROTECT)
    exchange_rate = models.DecimalField(max_digits=19, decimal_places=6, default=1)
    amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    discount_taken = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    batch = models.ForeignKey(
        PaymentBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
    )
    journal = models.ForeignKey(
        'Journal',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ap_payments',
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_ap_payments',
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_ap_payments',
    )

    class Meta:
        db_table = 'ap_payment'
        unique_together = ('organization', 'payment_number')
        ordering = ('-payment_date', '-payment_id')

    def __str__(self):
        return f"{self.payment_number} - {self.vendor.display_name}"


class APPaymentLine(models.Model):
    """Allocations from a payment to purchase invoices."""

    payment_line_id = models.BigAutoField(primary_key=True)
    payment = models.ForeignKey(
        APPayment,
        on_delete=models.CASCADE,
        related_name='lines',
    )
    invoice = models.ForeignKey(
        PurchaseInvoice,
        on_delete=models.PROTECT,
        related_name='payment_lines',
    )
    applied_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    discount_taken = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ap_payment_line'
        unique_together = ('payment', 'invoice')

    def __str__(self):
        return f"{self.payment.payment_number} -> {self.invoice.invoice_number}"


class PaymentApproval(models.Model):
    """Tracks approval decisions for payments."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    approval_id = models.BigAutoField(primary_key=True)
    payment = models.ForeignKey(
        APPayment,
        on_delete=models.CASCADE,
        related_name='approvals',
    )
    approver = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'ap_payment_approval'
        ordering = ('-decided_at', '-approval_id')



class SalesInvoice(models.Model):
    """Customer sales invoice header."""

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('validated', 'Validated'),
        ('posted', 'Posted'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ]

    invoice_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='sales_invoices',
    )
    customer = models.ForeignKey(
        'Customer',
        on_delete=models.PROTECT,
        related_name='sales_invoices',
    )
    customer_display_name = models.CharField(max_length=255)
    invoice_number = models.CharField(max_length=50, blank=True, default='')
    invoice_date = models.DateField()
    due_date = models.DateField()
    payment_term = models.ForeignKey(
        PaymentTerm,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'term_type__in': ['ar', 'both']},
    )
    currency = models.ForeignKey(
        'Currency',
        on_delete=models.PROTECT,
        related_name='sales_invoice_currency',
    )
    exchange_rate = models.DecimalField(max_digits=19, decimal_places=6, default=1)
    subtotal = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    tax_total = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    total = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    base_currency_total = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    reference_number = models.CharField(max_length=100, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    journal = models.ForeignKey(
        'Journal',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales_invoices',
    )
    ird_signature = models.CharField(max_length=512, null=True, blank=True)
    ird_ack_id = models.CharField(max_length=100, null=True, blank=True)
    ird_status = models.CharField(max_length=50, null=True, blank=True)
    ird_last_response = models.JSONField(default=dict, blank=True)
    ird_last_submitted_at = models.DateTimeField(null=True, blank=True)
    ird_fiscal_year_code = models.CharField(max_length=20, blank=True, default='')
    ird_is_realtime = models.BooleanField(default=True)
    ird_digital_payment_amount = models.DecimalField(max_digits=19, decimal_places=4, null=True, blank=True)
    ird_digital_payment_txn_id = models.CharField(max_length=100, blank=True, default='')
    ird_reprint_count = models.PositiveIntegerField(default=0)
    ird_last_printed_at = models.DateTimeField(null=True, blank=True)
    ird_last_reprint_reason = models.CharField(max_length=255, blank=True, default='')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_sales_invoices',
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_sales_invoices',
    )

    class Meta:
        db_table = 'sales_invoice'
        unique_together = ('organization', 'invoice_number')
        ordering = ('-invoice_date', '-invoice_id')
        indexes = [
            models.Index(fields=['organization', 'status']),
        ]

    def __str__(self):
        return f"{self.invoice_number} - {self.customer_display_name}"

    def recompute_totals(self, save=True):
        aggregates = self.lines.aggregate(
            subtotal=Sum('line_total'),
            tax_total=Sum('tax_amount'),
        )
        subtotal = aggregates.get('subtotal') or Decimal('0')
        tax_total = aggregates.get('tax_total') or Decimal('0')
        self.subtotal = subtotal
        self.tax_total = tax_total
        self.total = subtotal + tax_total
        self.base_currency_total = (self.total or Decimal('0')) * (self.exchange_rate or Decimal('1'))
        if save:
            super().save(update_fields=['subtotal', 'tax_total', 'total', 'base_currency_total', 'updated_at'])

    def clean(self):
        super().clean()
        if not self.pk:
            return
        original = SalesInvoice.objects.get(pk=self.pk)
        if original.status == 'posted' and original.invoice_number != self.invoice_number:
            raise ValidationError("Invoice number cannot be changed after posting.")

    def save(self, *args, **kwargs):
        if not self.invoice_number and self.organization_id:
            document_date = self.invoice_date or timezone.now().date()
            self.invoice_number = DocumentSequenceConfig.get_next_number(
                organization=self.organization,
                document_type='sales_invoice',
                document_date=document_date,
            )
        super().save(*args, **kwargs)


class SalesInvoiceLine(models.Model):
    """Sales invoice line items."""

    sales_invoice_line_id = models.BigAutoField(primary_key=True)
    invoice = models.ForeignKey(
        SalesInvoice,
        on_delete=models.CASCADE,
        related_name='lines',
    )
    line_number = models.PositiveIntegerField()
    description = models.TextField()
    product_code = models.CharField(max_length=100, blank=True)
    quantity = models.DecimalField(max_digits=19, decimal_places=4, default=1)
    unit_price = models.DecimalField(max_digits=19, decimal_places=6, default=0)
    discount_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    line_total = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    revenue_account = models.ForeignKey(
        ChartOfAccount,
        on_delete=models.PROTECT,
        related_name='sales_invoice_lines',
    )
    tax_code = models.ForeignKey(
        'TaxCode',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales_invoice_lines',
    )
    tax_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    cost_center = models.ForeignKey(
        'CostCenter',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    department = models.ForeignKey(
        'Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    project = models.ForeignKey(
        'Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    dimension_value = models.ForeignKey(
        'DimensionValue',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales_invoice_lines',
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sales_invoice_line'
        unique_together = ('invoice', 'line_number')
        ordering = ('invoice', 'line_number')

    def __str__(self):
        return f"{self.invoice.invoice_number} - line {self.line_number}"

    def clean(self):
        if self.quantity <= 0:
            raise ValidationError("Quantity must be greater than zero.")
        if self.unit_price < 0:
            raise ValidationError("Unit price cannot be negative.")
        super().clean()

    def save(self, *args, **kwargs):
        self.line_total = (self.quantity * self.unit_price) - (self.discount_amount or Decimal('0'))
        super().save(*args, **kwargs)


class ARReceipt(models.Model):
    """Cash/bank receipts applied to sales invoices."""

    receipt_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='ar_receipts',
    )
    customer = models.ForeignKey(
        'Customer',
        on_delete=models.PROTECT,
        related_name='ar_receipts',
    )
    receipt_number = models.CharField(max_length=50)
    receipt_date = models.DateField()
    payment_method = models.CharField(max_length=50, default='bank_transfer')
    reference = models.CharField(max_length=100, blank=True)
    currency = models.ForeignKey(
        'Currency',
        on_delete=models.PROTECT,
        related_name='ar_receipt_currency',
    )
    exchange_rate = models.DecimalField(max_digits=19, decimal_places=6, default=1)
    amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_ar_receipts',
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_ar_receipts',
    )

    class Meta:
        db_table = 'ar_receipt'
        unique_together = ('organization', 'receipt_number')
        ordering = ('-receipt_date', '-receipt_id')

    def __str__(self):
        return f"{self.receipt_number} - {self.customer.display_name}"


class ARReceiptLine(models.Model):
    """Allocations of a receipt against sales invoices."""

    receipt_line_id = models.BigAutoField(primary_key=True)
    receipt = models.ForeignKey(
        ARReceipt,
        on_delete=models.CASCADE,
        related_name='lines',
    )
    invoice = models.ForeignKey(
        SalesInvoice,
        on_delete=models.PROTECT,
        related_name='receipt_lines',
    )
    applied_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    discount_taken = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ar_receipt_line'
        unique_together = ('receipt', 'invoice')

    def __str__(self):
        return f"{self.receipt.receipt_number} -> {self.invoice.invoice_number}"

class Customer(models.Model):
    """Customer master data with credit information."""

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('prospect', 'Prospect'),
        ('on_hold', 'On Hold'),
        ('inactive', 'Inactive'),
    ]

    customer_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='customers',
    )
    code = models.CharField(max_length=30)
    display_name = models.CharField(max_length=255)
    legal_name = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    tax_id = models.CharField(max_length=50, blank=True)
    payment_term = models.ForeignKey(
        PaymentTerm,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'term_type__in': ['ar', 'both']},
    )
    default_currency = models.ForeignKey(
        'Currency',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='customer_currency',
    )
    accounts_receivable_account = models.ForeignKey(
        'ChartOfAccount',
        on_delete=models.PROTECT,
        related_name='customers_ar_account',
    )
    revenue_account = models.ForeignKey(
        'ChartOfAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='customers_revenue_account',
    )
    email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=50, blank=True)
    website = models.URLField(blank=True)
    credit_limit = models.DecimalField(max_digits=19, decimal_places=4, null=True, blank=True)
    credit_rating = models.CharField(max_length=20, blank=True)
    credit_review_at = models.DateField(null=True, blank=True)
    on_credit_hold = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_customers',
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_customers',
    )

    class Meta:
        db_table = 'customer'
        unique_together = ('organization', 'code')
        ordering = ('display_name',)

    def __str__(self):
        return f"{self.code} - {self.display_name}"

    def primary_address(self):
        return self.addresses.filter(is_primary=True).first() or self.addresses.first()

    def primary_contact(self):
        return self.contacts.filter(is_primary=True).first() or self.contacts.first()


class CustomerAddress(models.Model):
    """Customer mailing/shipping addresses."""

    address_id = models.BigAutoField(primary_key=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='addresses')
    address_type = models.CharField(max_length=20, default='billing')
    line1 = models.CharField(max_length=255)
    line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state_province = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country_code = models.CharField(max_length=2, default='US')
    is_primary = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'customer_address'
        indexes = [
            models.Index(fields=['customer', 'address_type']),
        ]

    def __str__(self):
        return f"{self.customer.display_name} - {self.address_type}"


class CustomerContact(models.Model):
    """Customer contact people."""

    contact_id = models.BigAutoField(primary_key=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='contacts')
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    mobile = models.CharField(max_length=50, blank=True)
    job_title = models.CharField(max_length=100, blank=True)
    is_primary = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'customer_contact'
        indexes = [
            models.Index(fields=['customer', 'is_primary']),
        ]

    def __str__(self):
        return f"{self.name} ({self.customer.display_name})"


class CustomerBankAccount(models.Model):
    """Banking instructions for inbound receipts."""

    bank_account_id = models.BigAutoField(primary_key=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='bank_accounts')
    bank_name = models.CharField(max_length=255)
    account_name = models.CharField(max_length=255)
    account_number = models.CharField(max_length=50)
    routing_number = models.CharField(max_length=50, blank=True)
    swift_code = models.CharField(max_length=20, blank=True)
    iban = models.CharField(max_length=34, blank=True)
    currency = models.ForeignKey(
        'Currency',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='customer_bank_currency',
    )
    is_primary = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'customer_bank_account'
        indexes = [
            models.Index(fields=['customer', 'is_primary']),
        ]

    def __str__(self):
        return f"{self.bank_name} - {self.account_number}"


class Dimension(models.Model):
    """Configurable analytic dimensions (cost center, department, custom, etc.)."""

    DIMENSION_TYPES = [
        ('cost_center', 'Cost Center'),
        ('department', 'Department'),
        ('project', 'Project'),
        ('custom', 'Custom'),
    ]

    dimension_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='dimensions',
    )
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    dimension_type = models.CharField(
        max_length=20,
        choices=DIMENSION_TYPES,
        default='custom',
    )
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_dimensions',
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_dimensions',
    )

    class Meta:
        db_table = 'dimension'
        unique_together = ('organization', 'code')
        ordering = ('name',)

    def __str__(self):
        return f"{self.code} - {self.name}"


class DimensionValue(models.Model):
    """Individual values for each dimension."""

    dimension_value_id = models.BigAutoField(primary_key=True)
    dimension = models.ForeignKey(Dimension, on_delete=models.CASCADE, related_name='values')
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'dimension_value'
        unique_together = ('dimension', 'code')
        ordering = ('dimension', 'code')

    def __str__(self):
        return f"{self.dimension.code}:{self.code}"
    @classmethod
    def get_next_code(cls, org_id, parent_id, account_type_id):
        from django.db.models import Q
        from django.db import transaction
        if not org_id:
            return None
        with transaction.atomic():
            if parent_id:
                try:
                    parent = cls.objects.get(pk=parent_id)
                except cls.DoesNotExist:
                    return None
                siblings = cls.objects.filter(parent_account=parent, organization_id=org_id)
                sibling_codes = siblings.values_list('account_code', flat=True)
                base_code = parent.account_code
                max_suffix = 0
                for code in sibling_codes:
                    if code.startswith(base_code + "."):
                        try:
                            suffix = int(code.replace(base_code + ".", ""))
                            if suffix > max_suffix:
                                max_suffix = suffix
                        except ValueError:
                            continue
                next_suffix = max_suffix + 1
                if next_suffix > MAX_COA_SIBLINGS:
                    raise ValidationError(
                        f"Maximum number of child accounts ({MAX_COA_SIBLINGS}) reached for this parent."
                    )
                return f"{base_code}.{next_suffix:02d}"
            else:
                from .models import AccountType
                try:
                    at = AccountType.objects.get(pk=account_type_id)
                except AccountType.DoesNotExist:
                    return None
                root_code = at.nature
                root_prefix = at.root_code_prefix or cls.NATURE_ROOT_CODE.get(root_code, '9000')
                step = at.root_code_step or cls.ROOT_STEP
                top_levels = cls.objects.filter(
                    parent_account__isnull=True,
                    organization_id=org_id,
                    account_code__startswith=root_prefix
                )
                max_code = 0
                for acc in top_levels:
                    try:
                        acc_num = int(acc.account_code)
                        if str(acc_num).startswith(root_prefix) and acc_num > max_code:
                            max_code = acc_num
                    except ValueError:
                        continue
                if max_code >= int(root_prefix):
                    next_code = max_code + step
                else:
                    next_code = int(root_prefix)
                return str(next_code).zfill(len(root_prefix))


# Backwards-compatibility alias
Account = ChartOfAccount


class CurrencyExchangeRate(models.Model):
    rate_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name='currency_exchange_rates', db_column='organization_id')
    from_currency = models.ForeignKey('Currency', on_delete=models.PROTECT, related_name='exchange_rates_from', db_column='from_currency_id')
    to_currency = models.ForeignKey('Currency', on_delete=models.PROTECT, related_name='exchange_rates_to', db_column='to_currency_id')
    rate_date = models.DateField()
    exchange_rate = models.DecimalField(max_digits=19, decimal_places=6)
    is_average_rate = models.BooleanField(default=False)
    source = models.CharField(max_length=50, default='manual')
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_exchange_rates')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_exchange_rates')
    rowversion = models.BinaryField(editable=False, null=True, blank=True, help_text="For MSSQL: ROWVERSION for optimistic concurrency.")
    archived_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='archived_exchange_rates')
    
    class Meta:
        db_table = 'currency_exchange_rate'
        unique_together = ('organization', 'from_currency', 'to_currency', 'rate_date')
        ordering = ['-rate_date']
        # For DBA: Composite UNIQUE (org, from, to, rate_date, is_average_rate)
        # For DBA: Clustered index (rate_date DESC, from_currency, to_currency)
        # For DBA: Partition by RANGE RIGHT (rate_date) when rows > 10M

    def __str__(self):
        return f"{self.from_currency.currency_code}/{self.to_currency.currency_code} @ {self.exchange_rate} on {self.rate_date}"


class JournalType(models.Model):
    journal_type_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='journal_types',
        db_column='organization_id',
    )
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    auto_numbering_prefix = models.CharField(max_length=10, null=True, blank=True)
    fiscal_year_prefix = models.BooleanField(default=False, help_text="If true, prefix with current fiscal year code.")
    auto_numbering_suffix = models.CharField(max_length=10, null=True, blank=True)
    sequence_next = models.BigIntegerField(default=1, help_text="Next available sequence number for auto-numbering.")
    sequence_padding = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text="Total digits for sequence portion when zero-padding.",
    )
    last_sequence_fiscal_year = models.ForeignKey(
        'FiscalYear',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='journal_types_last_sequence',
        help_text="Tracks the fiscal year that last consumed this sequence.",
    )
    is_system_type = models.BooleanField(default=False)
    requires_approval = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_journal_types')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_journal_types')
    rowversion = models.BinaryField(editable=False, null=True, blank=True, help_text="For MSSQL: ROWVERSION for optimistic concurrency.")
    archived_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='archived_journal_types')
    
    class Meta:
        db_table = 'journal_type'
        unique_together = ('organization', 'code')
        ordering = ('name',)
        # For DBA: Replace auto_numbering_next with CREATE SEQUENCE per (org, type)
        # For DBA: CHECK (requires_approval = 0 OR is_system_type = 0) if mutually exclusive
    def __str__(self):
        return f"{self.code} - {self.name}"

    def get_next_journal_number(self, period: AccountingPeriod = None) -> str:
        """Generate the next journal number for this type and increment the sequence."""
        from django.db import transaction

        """
        Generate the next journal number for this type and increment the sequence.
        Uses SELECT ... FOR UPDATE to ensure transactional, deterministic numbering.
        Race Handling: If two transactions try to get a number simultaneously,
        select_for_update will lock the row, making one wait. The first one
        gets the current sequence_next, increments it, and commits. The second
        then acquires the lock, sees the incremented sequence_next, and gets
        the next unique number.
        """
        from django.db import transaction
        from accounting.models import FiscalYear # Import here to avoid circular dependency

        with transaction.atomic():
            jt = JournalType.objects.select_for_update().get(pk=self.pk)

            prefix_parts = []
            fiscal_year = None
            if jt.fiscal_year_prefix:
                if period and getattr(period, "fiscal_year_id", None):
                    fiscal_year = period.fiscal_year
                else:
                    fiscal_year = FiscalYear.objects.filter(
                        organization=jt.organization, is_current=True
                    ).first()
                if fiscal_year:
                    prefix_parts.append(fiscal_year.code)
                    if jt.last_sequence_fiscal_year_id != fiscal_year.pk:
                        jt.sequence_next = 1
                        jt.last_sequence_fiscal_year = fiscal_year

            if jt.auto_numbering_prefix:
                prefix_parts.append(jt.auto_numbering_prefix)

            prefix = "".join(prefix_parts)
            suffix = jt.auto_numbering_suffix or ''

            next_num = jt.sequence_next
            jt.sequence_next = next_num + 1

            update_fields = ["sequence_next"]
            if jt.fiscal_year_prefix and fiscal_year:
                update_fields.append("last_sequence_fiscal_year")

            jt.save(update_fields=update_fields)

        padding = jt.sequence_padding or 3
        formatted_num = str(next_num).zfill(padding)
        return f"{prefix}{formatted_num}{suffix}"


class DocumentSequenceConfig(models.Model):
    """Configurable sequential numbering for business documents (invoices, notes)."""

    DOCUMENT_TYPES = [
        ('sales_invoice', 'Sales Invoice'),
        ('purchase_invoice', 'Purchase Invoice'),
        ('sales_credit_note', 'Sales Credit Note'),
        ('purchase_debit_note', 'Purchase Debit Note'),
    ]
    RESET_CHOICES = [
        ('fiscal_year', 'Fiscal Year'),
        ('never', 'Never'),
    ]
    DEFAULT_PREFIXES = {
        'sales_invoice': 'SI-',
        'purchase_invoice': 'PI-',
        'sales_credit_note': 'SCN-',
        'purchase_debit_note': 'PDN-',
    }

    sequence_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='document_sequences',
    )
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES)
    prefix = models.CharField(max_length=20, blank=True, default='')
    suffix = models.CharField(max_length=20, blank=True, default='')
    fiscal_year_prefix = models.BooleanField(
        default=True,
        help_text="If enabled, prepend the fiscal year code before the prefix.",
    )
    reset_policy = models.CharField(
        max_length=20,
        choices=RESET_CHOICES,
        default='fiscal_year',
        help_text="Determines when the sequence resets back to 1.",
    )
    sequence_next = models.BigIntegerField(default=1)
    sequence_padding = models.PositiveSmallIntegerField(
        default=4,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text="Digits reserved for the numeric component.",
    )
    last_sequence_fiscal_year = models.ForeignKey(
        FiscalYear,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='document_sequences_last_used',
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'document_sequence_config'
        unique_together = ('organization', 'document_type')
        ordering = ('organization', 'document_type')

    def __str__(self):
        return f"{self.organization.code} - {self.document_type}"

    @classmethod
    def get_or_create_sequence(cls, organization, document_type):
        defaults = {
            'prefix': cls.DEFAULT_PREFIXES.get(document_type, ''),
        }
        sequence, _ = cls.objects.get_or_create(
            organization=organization,
            document_type=document_type,
            defaults=defaults,
        )
        return sequence

    @classmethod
    def get_next_number(cls, *, organization, document_type, document_date=None):
        from django.db import transaction

        if organization is None:
            raise ValidationError("Organization is required to generate document numbers.")

        document_date = document_date or timezone.now().date()

        with transaction.atomic():
            try:
                sequence = (
                    cls.objects.select_for_update()
                    .get(organization=organization, document_type=document_type)
                )
            except cls.DoesNotExist:
                sequence = cls.get_or_create_sequence(organization, document_type)
                sequence = (
                    cls.objects.select_for_update()
                    .get(organization=organization, document_type=document_type)
                )

            fiscal_year = None
            if sequence.reset_policy == 'fiscal_year' or sequence.fiscal_year_prefix:
                fiscal_year = FiscalYear.get_for_date(organization, document_date)
                if (
                    fiscal_year
                    and sequence.reset_policy == 'fiscal_year'
                    and sequence.last_sequence_fiscal_year_id != fiscal_year.pk
                ):
                    sequence.sequence_next = 1
                    sequence.last_sequence_fiscal_year = fiscal_year

            next_value = sequence.sequence_next
            sequence.sequence_next = next_value + 1
            update_fields = ['sequence_next']
            if fiscal_year and sequence.reset_policy == 'fiscal_year':
                update_fields.append('last_sequence_fiscal_year')
            sequence.save(update_fields=update_fields)

        prefix_parts = []
        if sequence.fiscal_year_prefix and fiscal_year:
            prefix_parts.append(fiscal_year.code)
        if sequence.prefix:
            prefix_parts.append(sequence.prefix)
        prefix = ''.join(prefix_parts)
        suffix = sequence.suffix or ''
        number = str(next_value).zfill(sequence.sequence_padding or 1)
        return f"{prefix}{number}{suffix}"

class Journal(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('awaiting_approval', 'Awaiting Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('posted', 'Posted'),
        ('reversed', 'Reversed'),
    ]

    journal_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='journals'
    )
    journal_number = models.CharField(max_length=50)
    journal_type = models.ForeignKey(JournalType, on_delete=models.PROTECT)
    period = models.ForeignKey(AccountingPeriod, on_delete=models.PROTECT)
    journal_date = models.DateField()
    reference = models.CharField(max_length=100, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    currency_code = models.CharField(max_length=3, default='USD')
    exchange_rate = models.DecimalField(max_digits=19, decimal_places=6, default=1)
    total_debit = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    total_credit = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    posted_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='posted_journals')
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_journals',
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_journals')
    updated_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_journals')
    header_udf_data = models.JSONField(default=dict, blank=True)
    charges_data = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    is_locked = models.BooleanField(default=False)
    is_recurring = models.BooleanField(default=False)
    is_reversal = models.BooleanField(default=False)
    reversal_of = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reversal_entries',
        help_text="Links reversal journals back to the original entry.",
    )
    is_archived = models.BooleanField(default=False)
    schema_version = models.CharField(max_length=20, default="1.0.0") # Current schema version
    idempotency_key = models.CharField(max_length=255, unique=True, null=True, blank=True, help_text="Ensures idempotent journal submissions.")

    rowversion = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = [('organization', 'journal_number'), ('organization', 'idempotency_key')]
        ordering = ['-journal_date', '-journal_number']
        # For DBA: Partition monthly by journal_date
        permissions = [
            ("add_voucher_entry", "Can add voucher entry"),
            ("change_voucher_entry", "Can change voucher entry"),
            ("delete_voucher_entry", "Can delete voucher entry"),
            ("view_voucher_entry", "Can view voucher entry"),
            ("can_submit_for_approval", "Can submit journal for approval"),
            ("can_approve_journal", "Can approve journal"),
            ("can_post_journal", "Can post journal"),
            ("can_reverse_journal", "Can reverse journal"),
            ("can_reject_journal", "Can reject journal"),
            ("can_edit_journal", "Can edit journal"),
            ("can_reopen_period", "Can reopen accounting period"),
        ]
        constraints = [
            models.CheckConstraint(
                name='journal_balanced_when_posted',
                check=(
                    ~Q(status='posted')
                    | Q(total_debit=F('total_credit'))
                ),
            ),
        ]

    def __str__(self):
        return f"{self.journal_number} - {self.journal_type.name}"

    @property
    def imbalance(self):
        return self.total_debit - self.total_credit

    def update_totals(self):
        """Recalculates total_debit and total_credit from associated lines."""
        totals = self.lines.aggregate(
            total_debit=Sum('debit_amount'),
            total_credit=Sum('credit_amount')
        )
        self.total_debit = totals.get('total_debit') or 0
        self.total_credit = totals.get('total_credit') or 0

    def save(self, *args, **kwargs):
        from accounting.utils.audit import log_audit_event, get_changed_data
        
        is_new = not self.pk
        old_instance = None
        if not is_new:
            old_instance = Journal.objects.get(pk=self.pk)

        if old_instance and old_instance.is_locked and old_instance.status == "posted":
            protected_fields = [
                'journal_type_id',
                'period_id',
                'journal_date',
                'currency_code',
                'exchange_rate',
                'total_debit',
                'total_credit',
            ]
            for field in protected_fields:
                if getattr(self, field) != getattr(old_instance, field):
                    raise ValidationError("Posted journals are read-only and cannot be modified.")

        if not self.journal_number and self.journal_type:
            self.journal_number = self.journal_type.get_next_journal_number(period=self.period)
        
        if self.pk:
            self.update_totals()

        super().save(*args, **kwargs)

        if is_new:
            log_audit_event(self.created_by, self, 'created', changes=model_to_dict(self))
        else:
            changed_data = get_changed_data(old_instance, model_to_dict(self))
            if changed_data:
                log_audit_event(self.updated_by, self, 'updated', changes=changed_data)

class JournalLine(models.Model):
    journal_line_id = models.BigAutoField(primary_key=True)
    journal = models.ForeignKey(Journal, on_delete=models.CASCADE, related_name='lines')
    line_number = models.BigIntegerField()
    account = models.ForeignKey(ChartOfAccount, on_delete=models.PROTECT)
    description = models.TextField(null=True, blank=True)
    debit_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    credit_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    # Multi-currency fields
    txn_currency = models.ForeignKey('Currency', on_delete=models.PROTECT, related_name='journal_lines_txn', null=True, blank=True)
    fx_rate = models.DecimalField(max_digits=19, decimal_places=6, default=1)
    amount_txn = models.DecimalField(max_digits=19, decimal_places=4, default=0) # Amount in transaction currency
    amount_base = models.DecimalField(max_digits=19, decimal_places=4, default=0) # Amount in base currency (functional currency)
    # Original functional currency fields, renamed for clarity
    functional_debit_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    functional_credit_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True)
    project = models.ForeignKey('Project', on_delete=models.SET_NULL, null=True, blank=True)
    cost_center = models.ForeignKey('CostCenter', on_delete=models.SET_NULL, null=True, blank=True)
    dimensions = models.ManyToManyField(
        'DimensionValue',
        through='JournalLineDimension',
        related_name='journal_lines',
        blank=True,
    )
    tax_code = models.ForeignKey('TaxCode', on_delete=models.SET_NULL, null=True, blank=True)
    tax_rate = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    tax_amount = models.DecimalField(max_digits=19, decimal_places=4, null=True, blank=True)
    memo = models.TextField(null=True, blank=True)
    reconciled = models.BooleanField(default=False)
    reconciled_at = models.DateTimeField(null=True, blank=True)
    reconciled_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='reconciled_journal_lines')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_journal_lines')
    updated_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_journal_lines')
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='archived_journal_lines')
    rowversion = models.BinaryField(editable=False, null=True, blank=True, help_text="For MSSQL: ROWVERSION for optimistic concurrency.")
    udf_data = models.JSONField(default=dict, blank=True)
    class Meta:
        unique_together = ('journal', 'line_number')
        ordering = ['journal', 'line_number']
        # For DBA: Partition monthly by journal.journal_date
        # For DBA: Non-clustered index (account_id, period_id)
        # For DBA: CHECK (debit_amount = 0 OR credit_amount = 0)
        constraints = [
            models.CheckConstraint(
                name='journalline_single_sided',
                check=(
                    Q(debit_amount__gt=0, credit_amount=0)
                    | Q(credit_amount__gt=0, debit_amount=0)
                ),
            ),
        ]
    def __str__(self):
        return f"Line {self.line_number} of {self.journal.journal_number}"
    
    def clean(self):
        from django.core.exceptions import ValidationError
        debit = self.debit_amount or 0
        credit = self.credit_amount or 0
        if (debit == 0 and credit == 0) or (debit > 0 and credit > 0):
            raise ValidationError(
                "Line must have either debit or credit amount, not both or neither"
            )
        if self.tax_code:
            if self.tax_code.tax_type.filing_frequency == 'monthly' and self.journal.period.period_type == 'monthly':
                raise ValidationError(
                    "Tax code filing frequency must match journal period type"
                )
        super().clean()

    def save(self, *args, **kwargs):
        from accounting.utils.audit import log_audit_event, get_changed_data
        from django.forms.models import model_to_dict

        is_new = not self.pk
        old_instance = None
        if not is_new:
            old_instance = JournalLine.objects.get(pk=self.pk)

        super().save(*args, **kwargs)

        if is_new:
            log_audit_event(self.created_by, self, 'created', changes=model_to_dict(self))
        else:
            changed_data = get_changed_data(old_instance, model_to_dict(self))
            if changed_data:
                log_audit_event(self.updated_by, self, 'updated', changes=changed_data)


class JournalLineDimension(models.Model):
    """Links journal lines to flexible analytic dimensions."""

    journal_line = models.ForeignKey(
        JournalLine,
        on_delete=models.CASCADE,
        related_name='dimension_assignments',
    )
    dimension = models.ForeignKey(
        Dimension,
        on_delete=models.PROTECT,
        related_name='dimension_assignments',
    )
    dimension_value = models.ForeignKey(
        DimensionValue,
        on_delete=models.PROTECT,
        related_name='dimension_assignments',
    )
    allocation_percent = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        null=True,
        blank=True,
        help_text='Optional allocation weighting for reporting (0-100).',
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'journal_line_dimension'
        unique_together = ('journal_line', 'dimension')
        indexes = [
            models.Index(fields=['journal_line', 'dimension']),
        ]

    def __str__(self):
        return f"{self.journal_line_id} -> {self.dimension_value}"


class MonthlyJournalLineSummary(models.Model):
    """Pre-aggregated monthly journal line balances for faster reporting."""

    month_start = models.DateField()
    account = models.ForeignKey(
        ChartOfAccount,
        on_delete=models.DO_NOTHING,
        related_name='monthly_summaries',
    )
    total_debit = models.DecimalField(max_digits=19, decimal_places=4)
    total_credit = models.DecimalField(max_digits=19, decimal_places=4)

    class Meta:
        managed = False
        db_table = 'accounting_monthly_journalline_mv'
        ordering = ['-month_start', 'account']
        indexes = [
            models.Index(fields=['month_start', 'account']),
        ]

    @property
    def net_balance(self):
        return (self.total_debit or 0) - (self.total_credit or 0)

    def __str__(self):
        return f"{self.month_start} - {self.account}"

class TaxAuthority(models.Model):
    authority_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name='tax_authorities', db_column='organization_id')
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    country_code = models.CharField(max_length=2, null=True, blank=True)
    identifier = models.CharField(max_length=100, null=True, blank=True)
    contact_info = models.TextField(null=True, blank=True)
    api_endpoint = models.CharField(max_length=255, null=True, blank=True)
    api_key = models.CharField(max_length=255, null=True, blank=True)
    is_default = models.BooleanField(default=False)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_tax_authorities')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_tax_authorities')
    rowversion = models.BinaryField(editable=False, null=True, blank=True, help_text="For MSSQL: ROWVERSION for optimistic concurrency.")
    archived_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='archived_tax_authorities')

    class Meta:
        db_table = 'tax_authority'
        unique_together = ('organization', 'code')
        verbose_name_plural = "Tax Authorities"
        
    def __str__(self):
        return f"{self.code} - {self.name}"
    def save(self, *args, **kwargs):
        if not self.code:
            code_generator = AutoIncrementCodeGenerator(
                TaxAuthority,
                'code',
                organization=self.organization,
                prefix='TA',
                suffix='',
            )
            self.code = code_generator.generate_code()
        super(TaxAuthority, self).save(*args, **kwargs)


class TaxType(models.Model):
    FILING_FREQUENCY_CHOICES = [
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('annually', 'Annually'),
    ]
    
    tax_type_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name='tax_types', db_column='organization_id')
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    authority = models.ForeignKey('TaxAuthority', on_delete=models.SET_NULL, null=True, blank=True, db_column='authority_id')
    filing_frequency = models.CharField(max_length=50, choices=FILING_FREQUENCY_CHOICES, null=True, blank=True)
    is_system_type = models.BooleanField(default=False)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_tax_types')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_tax_types')
    rowversion = models.BinaryField(editable=False, null=True, blank=True, help_text="For MSSQL: ROWVERSION for optimistic concurrency.")
    archived_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='archived_tax_types')

    class Meta:
        db_table = 'tax_type'
        unique_together = ('organization', 'code')

    def __str__(self):
        return f"{self.code} - {self.name}"
    def save(self, *args, **kwargs):
        if not self.code:
            code_generator = AutoIncrementCodeGenerator(
                TaxType,
                'code',
                organization=self.organization,
                prefix='TT',
                suffix='',
            )
            self.code = code_generator.generate_code()
        super(TaxType, self).save(*args, **kwargs)

class TaxCode(models.Model):
    tax_code_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name='tax_codes', db_column='organization_id')
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    tax_type = models.ForeignKey('TaxType', on_delete=models.PROTECT, db_column='tax_type_id')
    description = models.TextField(null=True, blank=True)
    tax_rate = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    rate = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    is_recoverable = models.BooleanField(default=True)
    is_compound = models.BooleanField(default=False)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    sales_account = models.ForeignKey('ChartOfAccount', on_delete=models.SET_NULL, null=True, blank=True, related_name='sales_tax_codes', db_column='sales_account_id')
    purchase_account = models.ForeignKey('ChartOfAccount', on_delete=models.SET_NULL, null=True, blank=True, related_name='purchase_tax_codes', db_column='purchase_account_id')
    report_line_code = models.CharField(max_length=50, null=True, blank=True)
    tax_authority = models.ForeignKey('TaxAuthority', on_delete=models.PROTECT, null=True, blank=True, db_column='tax_authority_id')
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_tax_codes')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_tax_codes')
    rowversion = models.BinaryField(editable=False, null=True, blank=True, help_text="For MSSQL: ROWVERSION for optimistic concurrency.")
    archived_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='archived_tax_codes')

    class Meta:
        db_table = 'tax_code'
        unique_together = ('organization', 'code')

    def __str__(self):
        return f"{self.code} - {self.name}"
    def save(self, *args, **kwargs):
        if not self.code:
            code_generator = AutoIncrementCodeGenerator(
                TaxCode,
                'code',
                organization=self.organization,
                prefix='TC',
                suffix='',
            )
            self.code = code_generator.generate_code()
        super(TaxCode, self).save(*args, **kwargs)


class TaxCodeGroup(models.Model):
    """Bundle multiple tax codes for reuse in rules."""

    tax_code_group_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='tax_code_groups',
        db_column='organization_id',
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    tax_codes = models.ManyToManyField('TaxCode', related_name='tax_code_groups', blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tax_code_group'
        unique_together = ('organization', 'name')
        ordering = ('name',)

    def __str__(self):
        return self.name


class TaxRule(models.Model):
    """Declarative tax rule registry for context-aware tax selection."""

    ENTRY_MODE_CHOICES = [
        ('sale', 'Sale'),
        ('purchase', 'Purchase'),
        ('journal', 'Journal'),
    ]

    tax_rule_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='tax_rules',
        db_column='organization_id',
    )
    name = models.CharField(max_length=150)
    entry_mode = models.CharField(max_length=20, choices=ENTRY_MODE_CHOICES, null=True, blank=True)
    country_code = models.CharField(max_length=2, blank=True)
    state_code = models.CharField(max_length=10, blank=True)
    city = models.CharField(max_length=100, blank=True)
    product_category = models.CharField(max_length=100, blank=True)
    customer_type = models.CharField(max_length=100, blank=True)
    vendor_type = models.CharField(max_length=100, blank=True)
    industry_code = models.CharField(max_length=100, blank=True)
    priority = models.PositiveIntegerField(default=100)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    tax_code_group = models.ForeignKey(
        TaxCodeGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tax_rules',
    )
    tax_codes = models.ManyToManyField('TaxCode', related_name='tax_rules', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tax_rule'
        ordering = ('priority', 'tax_rule_id')
        indexes = [
            models.Index(fields=['organization', 'entry_mode']),
            models.Index(fields=['organization', 'country_code', 'state_code']),
            models.Index(fields=['organization', 'is_active']),
        ]

    def __str__(self):
        return self.name


class InvoiceLineTax(models.Model):
    """
    Stores per-line tax breakdown to support multiple/compound taxes.
    Generic FK is used so the same table can serve sales and purchase lines.
    """

    invoice_line_tax_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='invoice_line_taxes',
        db_column='organization_id',
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    line_object = GenericForeignKey('content_type', 'object_id')
    tax_code = models.ForeignKey('TaxCode', on_delete=models.PROTECT, related_name='invoice_line_taxes')
    sequence = models.PositiveIntegerField(default=1)
    base_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    tax_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'invoice_line_tax'
        ordering = ('content_type', 'object_id', 'sequence')
        unique_together = ('content_type', 'object_id', 'tax_code', 'sequence')
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['organization']),
        ]

    def __str__(self):
        return f"{self.tax_code.code} ({self.base_amount}->{self.tax_amount})"




def default_ui_schema():
    """
    Returns a default UI schema for voucher entry forms.
    This schema can be extended or overridden per VoucherModeConfig.
    """
    return {
        "header": {
            "journal_date": {
                "type": "date",
                "label": "Date",
                "required": True,
                "kwargs": {
                    "widget": {
                        "attrs": {
                            "class": "form-control datepicker"
                        }
                    }
                }
            },
            "journal_type": {
                "type": "select",
                "label": "Journal Type",
                "required": True,
                "choices": "JournalType",  # Reference to model or dynamic choices
                "kwargs": {
                    "widget": {
                        "attrs": {
                            "class": "form-control"
                        }
                    }
                }
            },
            "reference_number": {
                "type": "text",
                "label": "Reference Number",
                "required": False,
                "kwargs": {
                    "widget": {
                        "attrs": {
                            "class": "form-control"
                        }
                    }
                }
            },
            "description": {
                "type": "textarea",
                "label": "Description",
                "required": False,
                "kwargs": {
                    "widget": {
                        "attrs": {
                            "class": "form-control"
                        }
                    }
                }
            },
            "currency": {
                "type": "select",
                "label": "Currency",
                "required": True,
                "choices": "Currency",  # Reference to model or dynamic choices
                "kwargs": {
                    "widget": {
                        "attrs": {
                            "class": "form-control"
                        }
                    }
                }
            },
        },
        "lines": {
            "account": {
                "type": "autocomplete",
                "label": "Account",
                "required": True,
                "choices": "ChartOfAccount",  # Reference to model or dynamic choices
                "kwargs": {
                    "widget": {
                        "attrs": {
                            "class": "form-control account-autocomplete"
                        }
                    }
                }
            },
            "description": {
                "type": "text",
                "label": "Line Description",
                "required": False,
                "kwargs": {
                    "widget": {
                        "attrs": {
                            "class": "form-control"
                        }
                    }
                }
            },
            "debit_amount": {
                "type": "decimal",
                "label": "Debit",
                "required": False,
                "kwargs": {
                    "widget": {
                        "attrs": {
                            "class": "form-control amount-field"
                        }
                    }
                }
            },
            "credit_amount": {
                "type": "decimal",
                "label": "Credit",
                "required": False,
                "kwargs": {
                    "widget": {
                        "attrs": {
                            "class": "form-control amount-field"
                        }
                    }
                }
            },
            "tax_code": {
                "type": "select",
                "label": "Tax Code",
                "required": False,
                "choices": "TaxCode",  # Reference to model or dynamic choices
                "kwargs": {
                    "widget": {
                        "attrs": {
                            "class": "form-control"
                        }
                    }
                }
            },
            "department": {
                "type": "select",
                "label": "Department",
                "required": False,
                "choices": "Department",  # Reference to model or dynamic choices
                "kwargs": {
                    "widget": {
                        "attrs": {
                            "class": "form-control"
                        }
                    }
                }
            },
            "project": {
                "type": "select",
                "label": "Project",
                "required": False,
                "choices": "Project",  # Reference to model or dynamic choices
                "kwargs": {
                    "widget": {
                        "attrs": {
                            "class": "form-control"
                        }
                    }
                }
            },
            "cost_center": {
                "type": "select",
                "label": "Cost Center",
                "required": False,
                "choices": "CostCenter",  # Reference to model or dynamic choices
                "kwargs": {
                    "widget": {
                        "attrs": {
                            "class": "form-control"
                        }
                    }
                }
            },
        }
    }
    

class VoucherModeConfig(models.Model):
    LAYOUT_CHOICES = [
        ('standard', 'Standard'),
        ('compact', 'Compact'),
        ('detailed', 'Detailed'),
    ]
    
    config_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name='voucher_mode_configs', db_column='organization_id')
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    journal_type = models.ForeignKey('JournalType', on_delete=models.CASCADE, null=True, blank=True, db_column='journal_type_id')
    is_default = models.BooleanField(default=False)
    layout_style = models.CharField(max_length=20, choices=LAYOUT_CHOICES, default='standard')
    show_account_balances = models.BooleanField(default=True)
    show_tax_details = models.BooleanField(default=True)
    show_dimensions = models.BooleanField(default=True)
    allow_multiple_currencies = models.BooleanField(default=False)
    require_line_description = models.BooleanField(default=True)
    default_currency = models.CharField(max_length=3, default='USD')

    # New fields for Voucher Type Default Automation
    default_ledger = models.ForeignKey('ChartOfAccount', on_delete=models.SET_NULL, null=True, blank=True, related_name='default_for_voucher_configs')
    default_narration_template = models.TextField(null=True, blank=True, help_text="Template for default narration. Use placeholders like [PartyName].")
    default_voucher_mode = models.CharField(max_length=20, choices=[('single_entry', 'Single Entry'), ('double_entry', 'Double Entry')], null=True, blank=True)
    default_cost_center = models.ForeignKey('CostCenter', on_delete=models.SET_NULL, null=True, blank=True, related_name='default_for_voucher_configs')
    default_tax_ledger = models.ForeignKey('ChartOfAccount', on_delete=models.SET_NULL, null=True, blank=True, related_name='tax_ledger_for_voucher_configs', limit_choices_to={'is_control_account': True, 'control_account_type': 'tax'})

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_voucher_configs')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_voucher_configs')
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    rowversion = models.BinaryField(editable=False, null=True, blank=True, help_text="For MSSQL: ROWVERSION for optimistic concurrency.")
    archived_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='archived_voucher_configs')
    ui_schema = models.JSONField(
        default=default_ui_schema,
        blank=True
    )
    rowversion = models.PositiveIntegerField(default=1)
    validation_rules = models.JSONField(default=dict, blank=True)

    def resolve_ui(self):
        """Return cleaned schema merged with system defaults."""
        default = {"header": {}, "lines": {}}
        merged = {**default, **(self.ui_schema or {})}
        # Add any implicit fields your engine always needs here if required
        return merged
    
    class Meta:
        db_table = 'voucher_mode_config'
        unique_together = ('organization', 'code')
        
    def __str__(self):
        return f"{self.code} - {self.name}"
    def save(self, *args, **kwargs):
        if not self.code:
            code_generator = AutoIncrementCodeGenerator(
                VoucherModeConfig,
                'code',
                organization=self.organization,
                prefix='VM',
                suffix='',
            )
            self.code = code_generator.generate_code()
        super(VoucherModeConfig, self).save(*args, **kwargs)

# Added missing model from second file
class VoucherModeDefault(models.Model):
    default_id = models.BigAutoField(primary_key=True)
    config = models.ForeignKey('VoucherModeConfig', on_delete=models.CASCADE, related_name='defaults', db_column='config_id')
    account = models.ForeignKey('ChartOfAccount', on_delete=models.CASCADE, null=True, blank=True, db_column='account_id')
    account_type = models.ForeignKey('AccountType', on_delete=models.CASCADE, null=True, blank=True, db_column='account_type_id')
    default_debit = models.BooleanField(default=False)
    default_credit = models.BooleanField(default=False)
    default_amount = models.DecimalField(max_digits=19, decimal_places=4, null=True, blank=True)
    default_tax_code = models.ForeignKey('TaxCode', on_delete=models.SET_NULL, null=True, blank=True, db_column='default_tax_code_id')
    default_department = models.BigIntegerField(default=0)
    default_project = models.BigIntegerField(default=0)
    default_cost_center = models.BigIntegerField(default=0)
    default_description = models.TextField(null=True, blank=True)
    is_required = models.BooleanField(default=False)
    display_order = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_voucherdefaultconfigs')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_voucherdefaultconfigs')
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    rowversion = models.BinaryField(editable=False, null=True, blank=True, help_text="For MSSQL: ROWVERSION for optimistic concurrency.")
    archived_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='archived_voucher_default_configs')

    class Meta:
        db_table = 'voucher_mode_default'
        ordering = ['display_order']

    def __str__(self):
        return f"{self.config.name} - {self.account.account_name if self.account else self.account_type.name if self.account_type else 'Default'}"


class VoucherUDFConfig(models.Model):
    """User-Defined Fields configuration for voucher entry forms"""
    FIELD_TYPE_CHOICES = [
        ('text', 'Text'),
        ('number', 'Number'),
        ('decimal', 'Decimal'),
        ('date', 'Date'),
        ('datetime', 'Date & Time'),
        ('select', 'Dropdown'),
        ('multiselect', 'Multi-Select'),
        ('checkbox', 'Checkbox'),
        ('textarea', 'Text Area'),
        ('email', 'Email'),
        ('phone', 'Phone'),
        ('url', 'URL'),
    ]
    
    SCOPE_CHOICES = [
        ('header', 'Voucher Header'),
        ('line', 'Journal Line'),
    ]
    
    udf_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name='voucher_udf_configs', db_column='organization_id')
    voucher_mode = models.ForeignKey('VoucherModeConfig', on_delete=models.CASCADE, related_name='udf_configs', db_column='voucher_mode_id')
    field_name = models.CharField(max_length=50, help_text="Internal field name (no spaces, lowercase)")
    display_name = models.CharField(max_length=100, help_text="User-friendly display name")
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES, default='text')
    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES, default='header')
    is_required = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    default_value = models.CharField(max_length=255, blank=True, null=True)
    is_conditional = models.BooleanField(default=False)
    condition_json = models.JSONField(blank=True, null=True)
    choices = models.JSONField(null=True, blank=True, help_text="For select/multiselect fields")
    min_value = models.DecimalField(max_digits=19, decimal_places=4, null=True, blank=True)
    max_value = models.DecimalField(max_digits=19, decimal_places=4, null=True, blank=True)
    min_length = models.IntegerField(null=True, blank=True)
    max_length = models.IntegerField(null=True, blank=True)
    validation_regex = models.CharField(max_length=255, null=True, blank=True)
    help_text = models.TextField(null=True, blank=True)
    display_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_voucher_udfs')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_voucher_udfs')
    rowversion = models.BinaryField(editable=False, null=True, blank=True, help_text="For MSSQL: ROWVERSION for optimistic concurrency.")
    archived_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='archived_voucher_udfs')

    class Meta:
        db_table = 'voucher_udf_config'
        unique_together = ('voucher_mode', 'field_name')
        ordering = ['scope', 'display_order', 'field_name']
        verbose_name = "Voucher UDF Configuration"
        verbose_name_plural = "Voucher UDF Configurations"
    
    def __str__(self):
        return f"{self.voucher_mode.name} - {self.display_name}"
    
    def clean(self):
        from django.core.exceptions import ValidationError
        
        # Validate field name format
        if not re.match(r'^[a-z][a-z0-9_]*$', self.field_name):
            raise ValidationError("Field name must start with a letter and contain only lowercase letters, numbers, and underscores.")
        
        # Validate choices for select fields
        if self.field_type in ['select', 'multiselect'] and not self.choices:
            raise ValidationError("Choices are required for select and multiselect fields.")
        
        # Validate numeric constraints
        if self.field_type in ['number', 'decimal']:
            if self.min_value is not None and self.max_value is not None:
                if self.min_value > self.max_value:
                    raise ValidationError("Minimum value cannot be greater than maximum value.")
        
        # Validate length constraints
        if self.min_length is not None and self.max_length is not None:
            if self.min_length > self.max_length:
                raise ValidationError("Minimum length cannot be greater than maximum length.")
    
    def get_field_widget_attrs(self):
        """Get widget attributes for form rendering"""
        attrs = {
            'class': 'form-control',
            'data-field-type': self.field_type,
            'data-field-name': self.field_name,
        }
        
        if self.is_required:
            attrs['required'] = 'required'
        
        if self.help_text:
            attrs['title'] = self.help_text
        
        if self.field_type == 'number':
            if self.min_value is not None:
                attrs['min'] = str(self.min_value)
            if self.max_value is not None:
                attrs['max'] = str(self.max_value)
        elif self.field_type == 'decimal':
            attrs['step'] = '0.01'
            if self.min_value is not None:
                attrs['min'] = str(self.min_value)
            if self.max_value is not None:
                attrs['max'] = str(self.max_value)
        elif self.field_type in ['text', 'textarea']:
            if self.min_length is not None:
                attrs['minlength'] = str(self.min_length)
            if self.max_length is not None:
                attrs['maxlength'] = str(self.max_length)
        elif self.field_type == 'date':
            attrs['type'] = 'date'
        elif self.field_type == 'datetime':
            attrs['type'] = 'datetime-local'
        elif self.field_type == 'email':
            attrs['type'] = 'email'
        elif self.field_type == 'phone':
            attrs['type'] = 'tel'
        elif self.field_type == 'url':
            attrs['type'] = 'url'
        elif self.field_type == 'textarea':
            attrs['rows'] = '3'
        
        return attrs

class GeneralLedger(models.Model):
    gl_entry_id = models.BigAutoField(primary_key=True)
    organization_id = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='general_ledgers'
    )
    account = models.ForeignKey(ChartOfAccount, on_delete=models.PROTECT)
    journal = models.ForeignKey(Journal, on_delete=models.PROTECT)
    journal_line = models.ForeignKey(JournalLine, on_delete=models.PROTECT, related_name='gl_entries')
    period = models.ForeignKey(AccountingPeriod, on_delete=models.PROTECT)
    transaction_date = models.DateField()
    debit_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    credit_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    balance_after = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    currency_code = models.CharField(max_length=3, default='USD')
    exchange_rate = models.DecimalField(max_digits=19, decimal_places=6, default=1)
    functional_debit_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    functional_credit_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True)
    project = models.ForeignKey('Project', on_delete=models.SET_NULL, null=True, blank=True)
    cost_center = models.ForeignKey('CostCenter', on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    source_module = models.CharField(max_length=50, null=True, blank=True)
    source_reference = models.CharField(max_length=100, null=True, blank=True)
    is_adjustment = models.BooleanField(default=False)
    is_closing_entry = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='archived_general_ledgers')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_general_ledgers')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_general_ledgers')
    rowversion = models.BinaryField(editable=False, null=True, blank=True, help_text="For MSSQL: ROWVERSION for optimistic concurrency.")
    
    class Meta:
        ordering = ['transaction_date', 'created_at']
        indexes = [
            models.Index(fields=['account', 'transaction_date']),
            models.Index(fields=['transaction_date', 'account']),
        ]
        # For DBA: CLUSTERED COLUMNSTORE once >10M rows; narrow row-store NC index on (org, account, transaction_date)
        # For DBA: Monthly partitioning; move cold partitions to slower filegroup
        # For DBA: Make balance_after a PERSISTED computed column

    def __str__(self):
        return f"GL Entry {self.gl_entry_id} for {self.account.account_code}"

class Attachment(models.Model):
    attachment_id = models.BigAutoField(primary_key=True)
    journal = models.ForeignKey(Journal, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='attachments/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Attachment for Journal {self.journal.journal_number}"

class Approval(models.Model):
    approval_id = models.BigAutoField(primary_key=True)
    journal = models.ForeignKey(Journal, on_delete=models.CASCADE, related_name='approvals')
    approver = models.ForeignKey(CustomUser, on_delete=models.PROTECT)
    approved_at = models.DateTimeField(auto_now_add=True)
    comments = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ('journal', 'approver')

    def __str__(self):
        return f"Approval for Journal {self.journal.journal_number} by {self.approver.username}"


# -----------------------------
# Generic UDF (user-defined field) subsystem
# -----------------------------
class UDFDefinition(models.Model):
    """Metadata for dynamic fields attachable to any model via content types."""

    FIELD_TYPE_CHOICES = [
        ('text', 'Text'),
        ('number', 'Number'),
        ('decimal', 'Decimal'),
        ('date', 'Date'),
        ('datetime', 'DateTime'),
        ('boolean', 'Boolean'),
        ('select', 'Select'),
        ('multiselect', 'MultiSelect'),
        ('json', 'JSON'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name='udf_definitions')
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    field_name = models.CharField(max_length=50, help_text="Internal field name (no spaces)")
    display_name = models.CharField(max_length=100, help_text="Field label")
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES, default='text')
    is_required = models.BooleanField(default=False)
    is_filterable = models.BooleanField(default=False)
    is_pivot_dim = models.BooleanField(default=False)
    choices = models.JSONField(null=True, blank=True, help_text="For select/multiselect options")
    default_value = models.CharField(max_length=255, blank=True, null=True)
    help_text = models.TextField(blank=True, null=True)
    min_value = models.DecimalField(max_digits=19, decimal_places=4, null=True, blank=True)
    max_value = models.DecimalField(max_digits=19, decimal_places=4, null=True, blank=True)
    min_length = models.IntegerField(null=True, blank=True)
    max_length = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udf_definition'
        unique_together = ('content_type', 'field_name', 'organization')
        ordering = ['content_type', 'field_name']

    def __str__(self):
        return f"{self.display_name} ({self.field_name})"

    def get_field_widget_attrs(self) -> dict:
        """Return HTML widget attributes derived from definition metadata."""
        attrs: dict[str, object] = {}
        if self.max_length:
            attrs.setdefault("maxlength", int(self.max_length))
        if self.min_length:
            attrs.setdefault("minlength", int(self.min_length))
        if self.help_text and self.field_type in {"text", "number", "decimal", "select", "multiselect"}:
            attrs.setdefault("title", self.help_text)
        if self.default_value and self.field_type in {"text", "number", "decimal"}:
            attrs.setdefault("placeholder", str(self.default_value))
        metadata = getattr(self, "metadata", None)
        if isinstance(metadata, dict):
            attrs.update(metadata.get("widget_attrs", {}))
        return attrs


class UDFValue(models.Model):
    """EAV-style storage for UDF values linked to any model instance."""

    udf_definition = models.ForeignKey(UDFDefinition, on_delete=models.CASCADE, related_name='values')
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    value = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'udf_value'
        unique_together = ('udf_definition', 'content_type', 'object_id')

    def __str__(self):
        return f"UDF {self.udf_definition.field_name}={self.value}"

class RecurringJournal(models.Model):
    """
    Stores templates for recurring journal entries, inspired by Infor CloudSuite.
    """
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('annually', 'Annually'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('expired', 'Expired'),
    ]

    recurring_journal_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='recurring_journals')
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    interval = models.PositiveSmallIntegerField(default=1, help_text="e.g., every 2 months")
    day_of_month = models.PositiveSmallIntegerField(null=True, blank=True, help_text="1-31, for monthly/quarterly/annually")
    month_of_year = models.PositiveSmallIntegerField(null=True, blank=True, help_text="1-12, for annually")
    
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True, help_text="Leave blank for indefinite recurring journals")
    last_run_date = models.DateField(null=True, blank=True)
    next_run_date = models.DateField()

    journal_type = models.ForeignKey(JournalType, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_recurring_journals')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_recurring_journals')

    class Meta:
        db_table = 'recurring_journal'
        ordering = ['organization', 'name']
        unique_together = ('organization', 'code')

    def __str__(self):
        return f"{self.code} - {self.name}"

class RecurringJournalLine(models.Model):
    """
    Stores the line items for a recurring journal template.
    """
    recurring_journal_line_id = models.BigAutoField(primary_key=True)
    recurring_journal = models.ForeignKey(RecurringJournal, on_delete=models.CASCADE, related_name='lines')
    account = models.ForeignKey(ChartOfAccount, on_delete=models.PROTECT)
    description = models.TextField(blank=True, null=True)
    debit_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    credit_amount = models.DecimalField(max_digits=19, decimal_places=4, default=0)
    department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True)
    project = models.ForeignKey('Project', on_delete=models.SET_NULL, null=True, blank=True)
    cost_center = models.ForeignKey('CostCenter', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['recurring_journal', 'pk']

    def clean(self):
        if self.debit_amount > 0 and self.credit_amount > 0:
            raise ValidationError("A journal line cannot have both a debit and a credit amount.")
        if self.debit_amount == 0 and self.credit_amount == 0:
            raise ValidationError("A journal line must have either a debit or a credit amount.")


class RecurringEntry(RecurringJournal):
    """
    Alias for RecurringJournal for backward compatibility.
    Used by scheduled_task_views.py
    """
    class Meta:
        proxy = True
        verbose_name = "Recurring Entry"
        verbose_name_plural = "Recurring Entries"


class ScheduledReport(models.Model):
    """
    Configuration for scheduled report generation.
    """
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('annually', 'Annually'),
    ]
    
    REPORT_TYPE_CHOICES = [
        ('trial_balance', 'Trial Balance'),
        ('balance_sheet', 'Balance Sheet'),
        ('income_statement', 'Income Statement'),
        ('cash_flow', 'Cash Flow Statement'),
        ('general_ledger', 'General Ledger'),
        ('journal_report', 'Journal Report'),
    ]
    
    FORMAT_CHOICES = [
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
        ('csv', 'CSV'),
    ]
    
    report_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='scheduled_reports')
    name = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    report_type = models.CharField(max_length=50, choices=REPORT_TYPE_CHOICES)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    format = models.CharField(max_length=10, choices=FORMAT_CHOICES, default='pdf')
    
    # Schedule settings
    day_of_week = models.PositiveSmallIntegerField(null=True, blank=True, help_text="0-6 for weekly reports")
    day_of_month = models.PositiveSmallIntegerField(null=True, blank=True, help_text="1-31 for monthly reports")
    time_of_day = models.TimeField(default='09:00')
    
    # Recipients
    recipients = models.TextField(help_text="Comma-separated email addresses")
    
    # Report parameters (stored as JSON)
    parameters = models.JSONField(default=dict, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    last_run_date = models.DateTimeField(null=True, blank=True)
    next_run_date = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_scheduled_reports')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_scheduled_reports')
    
    class Meta:
        db_table = 'scheduled_report'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} - {self.get_frequency_display()}"


class ScheduledTaskExecution(models.Model):
    """
    Tracks execution history of scheduled tasks.
    """
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Running', 'Running'),
        ('Success', 'Success'),
        ('Failed', 'Failed'),
    ]
    
    TASK_TYPE_CHOICES = [
        ('period_close', 'Period Close'),
        ('recurring_entry', 'Recurring Entry'),
        ('scheduled_report', 'Scheduled Report'),
        ('data_export', 'Data Export'),
    ]
    
    execution_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='task_executions')
    task_type = models.CharField(max_length=50, choices=TASK_TYPE_CHOICES)
    task_name = models.CharField(max_length=200)
    
    # Task details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    executed_at = models.DateTimeField(auto_now_add=True)
    
    # Results
    result_message = models.TextField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    records_processed = models.IntegerField(default=0)
    
    # Celery task ID for async tasks
    celery_task_id = models.CharField(max_length=255, null=True, blank=True)
    
    # Audit
    triggered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='triggered_task_executions')
    
    class Meta:
        db_table = 'scheduled_task_execution'
        ordering = ['-executed_at']
        indexes = [
            models.Index(fields=['organization', 'task_type', '-executed_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.task_name} - {self.status} at {self.executed_at}"
    
    @property
    def duration(self):
        """Calculate task duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class ReportDefinition(models.Model):
    """
    Allows power users to register custom stored-procedure backed reports.
    """

    report_id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='report_definitions',
        help_text="Optional organization scope; null makes the report available to every tenant.",
    )
    code = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    stored_procedure = models.CharField(
        max_length=255,
        help_text="Name of the database function or stored procedure to call.",
    )
    parameter_schema = models.JSONField(
        default=dict,
        blank=True,
        help_text="Declarative parameter definitions for dynamic parameter forms.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_report_definitions',
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_report_definitions',
    )

    class Meta:
        db_table = 'report_definition'
        unique_together = ('organization', 'code')
        ordering = ['organization_id', 'code']

    def __str__(self):
        scope = self.organization.name if self.organization else 'Global'
        return f"{self.code} ({scope})"
