from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
import json

# Import VoucherModeConfig from its location (assumed to be in accounting.models)
from accounting.models import VoucherModeConfig


class VoucherSchemaStatus(models.TextChoices):
    """Status choices for schema workflow"""
    DRAFT = 'draft', 'Draft'
    PENDING_APPROVAL = 'pending_approval', 'Pending Approval'
    APPROVED = 'approved', 'Approved'
    PUBLISHED = 'published', 'Published'
    REJECTED = 'rejected', 'Rejected'
    ARCHIVED = 'archived', 'Archived'


class VoucherSchema(models.Model):
    """
    Stores versioned UI schemas for voucher forms with approval workflow.
    Each version represents a snapshot of the form design.
    """
    voucher_mode_config = models.ForeignKey(
        VoucherModeConfig, 
        on_delete=models.CASCADE, 
        related_name='schemas'
    )
    schema = models.JSONField(help_text="Complete form schema with fields, layout, and validation rules")
    version = models.PositiveIntegerField(default=1)
    
    # Workflow fields
    status = models.CharField(
        max_length=20, 
        choices=VoucherSchemaStatus.choices, 
        default=VoucherSchemaStatus.DRAFT
    )
    is_active = models.BooleanField(default=False, help_text="Only one version can be active at a time")
    
    # Change tracking
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL,
        related_name='created_schemas'
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL,
        related_name='updated_schemas'
    )
    
    # Approval workflow
    submitted_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL,
        related_name='submitted_schemas'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL,
        related_name='approved_schemas'
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL,
        related_name='rejected_schemas'
    )
    rejection_reason = models.TextField(null=True, blank=True)
    
    # Publishing
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL,
        related_name='published_schemas'
    )
    
    # Change notes
    change_notes = models.TextField(null=True, blank=True, help_text="Description of changes in this version")
    
    class Meta:
        db_table = 'forms_designer_voucher_schema'
        ordering = ['-created_at']
        unique_together = ('voucher_mode_config', 'version')
        indexes = [
            models.Index(fields=['voucher_mode_config', 'status']),
            models.Index(fields=['voucher_mode_config', 'is_active']),
        ]
    
    def __str__(self):
        return f"Schema v{self.version} for {self.voucher_mode_config} ({self.get_status_display()})"
    
    def clean(self):
        """Validate schema structure"""
        if not isinstance(self.schema, dict):
            raise ValidationError("Schema must be a valid JSON object")
        
        # Validate required schema keys
        required_keys = ['header', 'lines']
        for key in required_keys:
            if key not in self.schema:
                raise ValidationError(f"Schema must contain '{key}' key")
    
    def save(self, *args, **kwargs):
        # If this is being set as active, deactivate others
        if self.is_active:
            VoucherSchema.objects.filter(
                voucher_mode_config=self.voucher_mode_config,
                is_active=True
            ).exclude(pk=self.pk).update(is_active=False)
        
        super().save(*args, **kwargs)


class SchemaTemplate(models.Model):
    """
    Reusable form templates that can be applied to multiple voucher types
    """
    template_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    category = models.CharField(
        max_length=50, 
        choices=[
            ('standard', 'Standard'),
            ('payment', 'Payment'),
            ('receipt', 'Receipt'),
            ('journal', 'Journal'),
            ('custom', 'Custom'),
        ],
        default='custom'
    )
    schema = models.JSONField(help_text="Template schema structure")
    
    # Sharing and access
    is_system = models.BooleanField(default=False, help_text="System templates cannot be deleted")
    is_public = models.BooleanField(default=False, help_text="Available to all organizations")
    # Store organization by ID to avoid cross-app dependency issues
    organization_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Organization ID if template is organization-specific"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    usage_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'forms_designer_schema_template'
        ordering = ['category', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"
