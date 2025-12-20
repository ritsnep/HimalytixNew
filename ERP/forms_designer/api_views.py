"""
Enhanced API Views for Forms Designer
Comprehensive CRUD operations with workflow support
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.views.decorators.http import require_http_methods, require_POST
from django.http import JsonResponse
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Max
from utils.auth import get_user_organization
from django.core.exceptions import PermissionDenied

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from accounting.models import VoucherModeConfig, VoucherUDFConfig
from .models import VoucherSchema, SchemaTemplate, VoucherSchemaStatus
from .serializers import (
    VoucherUDFConfigSerializer, VoucherSchemaSerializer,
    SchemaTemplateSerializer, VoucherModeConfigListSerializer
)
from .utils import get_active_schema, save_schema
import json
import difflib
import logging

logger = logging.getLogger(__name__)


def _get_request_organization(request):
    """Return the active organization attached to this request."""
    organization = getattr(request, "organization", None)
    if organization:
        return organization
    user = getattr(request, "user", None)
    org = get_user_organization(user)
    if org and user and hasattr(user, "set_active_organization"):
        user.set_active_organization(org)
    return org


class OrganizationScopedViewMixin:
    """Common helpers for organization-aware viewsets."""

    def _get_organization(self):
        return _get_request_organization(self.request)

    def _require_organization(self):
        organization = self._get_organization()
        if not organization:
            raise PermissionDenied("Active organization required")
        return organization


class VoucherUDFConfigViewSet(OrganizationScopedViewMixin, viewsets.ModelViewSet):
    """
    ViewSet for UDF Configuration management
    Supports CRUD operations on User-Defined Fields
    """
    serializer_class = VoucherUDFConfigSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        organization = self._get_organization()
        if not organization:
            return VoucherUDFConfig.objects.none()

        queryset = VoucherUDFConfig.objects.filter(
            archived_at__isnull=True,
            organization=organization,
        )
        
        # Filter by voucher mode if provided
        voucher_mode_id = self.request.query_params.get('voucher_mode', None)
        if voucher_mode_id:
            queryset = queryset.filter(voucher_mode_id=voucher_mode_id)
        
        # Filter by scope
        scope = self.request.query_params.get('scope', None)
        if scope:
            queryset = queryset.filter(scope=scope)
        
        return queryset.order_by('scope', 'display_order', 'field_name')
    
    def perform_create(self, serializer):
        """Set organization and creator on create"""
        organization = self._require_organization()
        voucher_mode = serializer.validated_data.get('voucher_mode')
        if voucher_mode and voucher_mode.organization_id != getattr(organization, 'id', None):
            raise PermissionDenied("Voucher mode is not part of your organization")
        serializer.save(
            organization=organization,
            created_by=self.request.user
        )
    
    def perform_update(self, serializer):
        """Track who updated"""
        organization = self._require_organization()
        voucher_mode = serializer.validated_data.get('voucher_mode')
        if voucher_mode and voucher_mode.organization_id != getattr(organization, 'id', None):
            raise PermissionDenied("Voucher mode is not part of your organization")
        serializer.save(updated_by=self.request.user)
    
    def perform_destroy(self, instance):
        """Soft delete - set archived_at instead of actual deletion"""
        instance.archived_at = timezone.now()
        instance.archived_by = self.request.user
        instance.is_active = False
        instance.save()
    
    @action(detail=False, methods=['post'])
    def bulk_update_order(self, request):
        """Update display order for multiple fields"""
        try:
            updates = request.data.get('updates', [])
            
            with transaction.atomic():
                for update in updates:
                    udf_id = update.get('udf_id')
                    new_order = update.get('display_order')
                    
                    VoucherUDFConfig.objects.filter(
                        udf_id=udf_id
                    ).update(display_order=new_order)
            
            return Response({'message': 'Display order updated successfully'})
        except Exception as e:
            logger.error(f"Error updating display order: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def clone(self, request, pk=None):
        """Clone an existing UDF configuration"""
        try:
            source_udf = self.get_object()
            
            # Create a copy with modified name
            new_field_name = f"{source_udf.field_name}_copy"
            new_display_name = f"{source_udf.display_name} (Copy)"
            
            # Ensure uniqueness
            counter = 1
            while VoucherUDFConfig.objects.filter(
                voucher_mode=source_udf.voucher_mode,
                field_name=new_field_name
            ).exists():
                new_field_name = f"{source_udf.field_name}_copy_{counter}"
                new_display_name = f"{source_udf.display_name} (Copy {counter})"
                counter += 1
            
            cloned_udf = VoucherUDFConfig.objects.create(
                organization=source_udf.organization,
                voucher_mode=source_udf.voucher_mode,
                field_name=new_field_name,
                display_name=new_display_name,
                field_type=source_udf.field_type,
                scope=source_udf.scope,
                is_required=source_udf.is_required,
                default_value=source_udf.default_value,
                is_conditional=source_udf.is_conditional,
                condition_json=source_udf.condition_json,
                choices=source_udf.choices,
                min_value=source_udf.min_value,
                max_value=source_udf.max_value,
                min_length=source_udf.min_length,
                max_length=source_udf.max_length,
                validation_regex=source_udf.validation_regex,
                help_text=source_udf.help_text,
                display_order=source_udf.display_order + 1,
                created_by=request.user
            )
            
            serializer = self.get_serializer(cloned_udf)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            logger.error(f"Error cloning UDF: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class VoucherSchemaViewSet(OrganizationScopedViewMixin, viewsets.ModelViewSet):
    """
    ViewSet for Voucher Schema management
    Supports versioning, approval workflow, and publishing
    """
    serializer_class = VoucherSchemaSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        organization = self._get_organization()
        if not organization:
            return VoucherSchema.objects.none()

        queryset = VoucherSchema.objects.filter(
            voucher_mode_config__organization=organization
        )
        
        # Filter by voucher mode config
        config_id = self.request.query_params.get('config_id', None)
        if config_id:
            queryset = queryset.filter(voucher_mode_config_id=config_id)
        
        # Filter by status
        schema_status = self.request.query_params.get('status', None)
        if schema_status:
            queryset = queryset.filter(status=schema_status)
        
        # Filter active only
        active_only = self.request.query_params.get('active_only', None)
        if active_only == 'true':
            queryset = queryset.filter(is_active=True)
        
        return queryset.select_related(
            'voucher_mode_config',
            'created_by',
            'updated_by',
            'approved_by'
        ).order_by('-created_at')
    
    def perform_create(self, serializer):
        """Create new schema version"""
        voucher_mode_config = serializer.validated_data['voucher_mode_config']

        organization = self._require_organization()
        if voucher_mode_config.organization_id != getattr(organization, 'id', None):
            raise PermissionDenied("Config is not part of your organization")
        
        # Get next version number
        last_version = VoucherSchema.objects.filter(
            voucher_mode_config=voucher_mode_config
        ).aggregate(Max('version'))['version__max']
        
        next_version = (last_version or 0) + 1
        
        serializer.save(
            version=next_version,
            created_by=self.request.user,
            status=VoucherSchemaStatus.DRAFT
        )
    
    def perform_update(self, serializer):
        """Track updates"""
        organization = self._require_organization()
        new_config = serializer.validated_data.get('voucher_mode_config')
        if new_config and new_config.organization_id != getattr(organization, 'id', None):
            raise PermissionDenied("Config is not part of your organization")
        serializer.save(updated_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def submit_for_approval(self, request, pk=None):
        """Submit schema for approval"""
        schema = self.get_object()
        
        if schema.status != VoucherSchemaStatus.DRAFT:
            return Response(
                {'error': 'Only draft schemas can be submitted for approval'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user has permission
        if not request.user.has_perm('forms_designer.change_voucherschema'):
            raise PermissionDenied("You don't have permission to submit schemas")
        
        schema.status = VoucherSchemaStatus.PENDING_APPROVAL
        schema.submitted_at = timezone.now()
        schema.submitted_by = request.user
        schema.save()
        
        serializer = self.get_serializer(schema)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a schema"""
        schema = self.get_object()
        
        if schema.status != VoucherSchemaStatus.PENDING_APPROVAL:
            return Response(
                {'error': 'Only pending schemas can be approved'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user has approval permission
        if not request.user.has_perm('forms_designer.approve_voucherschema'):
            raise PermissionDenied("You don't have permission to approve schemas")
        
        schema.status = VoucherSchemaStatus.APPROVED
        schema.approved_at = timezone.now()
        schema.approved_by = request.user
        schema.save()
        
        serializer = self.get_serializer(schema)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a schema"""
        schema = self.get_object()
        
        if schema.status != VoucherSchemaStatus.PENDING_APPROVAL:
            return Response(
                {'error': 'Only pending schemas can be rejected'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user has approval permission
        if not request.user.has_perm('forms_designer.approve_voucherschema'):
            raise PermissionDenied("You don't have permission to reject schemas")
        
        rejection_reason = request.data.get('rejection_reason', '')
        
        schema.status = VoucherSchemaStatus.REJECTED
        schema.rejected_at = timezone.now()
        schema.rejected_by = request.user
        schema.rejection_reason = rejection_reason
        schema.save()
        
        serializer = self.get_serializer(schema)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """Publish an approved schema"""
        schema = self.get_object()
        
        # Admins can publish directly, others need approval first
        if not request.user.is_superuser and schema.status != VoucherSchemaStatus.APPROVED:
            return Response(
                {'error': 'Schema must be approved before publishing'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            # Deactivate all other versions
            VoucherSchema.objects.filter(
                voucher_mode_config=schema.voucher_mode_config,
                is_active=True
            ).update(is_active=False)
            
            # Publish and activate this version
            schema.status = VoucherSchemaStatus.PUBLISHED
            schema.published_at = timezone.now()
            schema.published_by = request.user
            schema.is_active = True
            schema.save()
            
            # Update the voucher mode config's schema_definition
            from accounting.voucher_schema import ui_schema_to_definition
            schema.voucher_mode_config.schema_definition = ui_schema_to_definition(schema.schema)
            schema.voucher_mode_config.save(update_fields=['schema_definition'])
        
        serializer = self.get_serializer(schema)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def revert(self, request, pk=None):
        """Revert to this schema version"""
        schema = self.get_object()
        
        if not request.user.has_perm('forms_designer.change_voucherschema'):
            raise PermissionDenied("You don't have permission to revert schemas")
        
        with transaction.atomic():
            # Create a new version based on this schema
            last_version = VoucherSchema.objects.filter(
                voucher_mode_config=schema.voucher_mode_config
            ).aggregate(Max('version'))['version__max']
            
            new_schema = VoucherSchema.objects.create(
                voucher_mode_config=schema.voucher_mode_config,
                schema=schema.schema,
                version=(last_version or 0) + 1,
                status=VoucherSchemaStatus.DRAFT,
                created_by=request.user,
                change_notes=f"Reverted to version {schema.version}"
            )
        
        serializer = self.get_serializer(new_schema)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def compare(self, request):
        """Compare two schema versions"""
        version1_id = request.query_params.get('version1')
        version2_id = request.query_params.get('version2')
        
        if not version1_id or not version2_id:
            return Response(
                {'error': 'Both version1 and version2 parameters are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            schema1 = VoucherSchema.objects.get(pk=version1_id)
            schema2 = VoucherSchema.objects.get(pk=version2_id)
            
            # Generate diff
            schema1_str = json.dumps(schema1.schema, indent=2, sort_keys=True)
            schema2_str = json.dumps(schema2.schema, indent=2, sort_keys=True)
            
            diff = list(difflib.unified_diff(
                schema1_str.splitlines(),
                schema2_str.splitlines(),
                fromfile=f'Version {schema1.version}',
                tofile=f'Version {schema2.version}',
                lineterm=''
            ))
            
            return Response({
                'version1': VoucherSchemaSerializer(schema1).data,
                'version2': VoucherSchemaSerializer(schema2).data,
                'diff': diff,
                'changes_summary': self._generate_changes_summary(schema1.schema, schema2.schema)
            })
        
        except VoucherSchema.DoesNotExist:
            return Response(
                {'error': 'One or both schemas not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def _generate_changes_summary(self, schema1, schema2):
        """Generate a human-readable summary of changes"""
        summary = {
            'header_fields_added': [],
            'header_fields_removed': [],
            'header_fields_modified': [],
            'line_fields_added': [],
            'line_fields_removed': [],
            'line_fields_modified': []
        }
        
        for section in ['header', 'lines']:
            fields1 = schema1.get(section, {})
            fields2 = schema2.get(section, {})
            
            # Convert to dict if list
            if isinstance(fields1, list):
                fields1 = {f.get('name'): f for f in fields1 if f.get('name')}
            if isinstance(fields2, list):
                fields2 = {f.get('name'): f for f in fields2 if f.get('name')}
            
            section_key = 'header' if section == 'header' else 'line'
            
            # Find added fields
            for field_name in set(fields2.keys()) - set(fields1.keys()):
                summary[f'{section_key}_fields_added'].append(field_name)
            
            # Find removed fields
            for field_name in set(fields1.keys()) - set(fields2.keys()):
                summary[f'{section_key}_fields_removed'].append(field_name)
            
            # Find modified fields
            for field_name in set(fields1.keys()) & set(fields2.keys()):
                if fields1[field_name] != fields2[field_name]:
                    summary[f'{section_key}_fields_modified'].append(field_name)
        
        return summary


class SchemaTemplateViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Schema Template management
    """
    serializer_class = SchemaTemplateSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = SchemaTemplate.objects.all()
        
        # Filter by category
        category = self.request.query_params.get('category', None)
        if category:
            queryset = queryset.filter(category=category)
        
        # Show public templates or user's organization templates
        if not self.request.user.is_superuser:
            org = _get_request_organization(self.request)
            if org:
                queryset = queryset.filter(
                    Q(is_public=True) |
                    Q(organization_id=getattr(org, 'id', None))
                )
            else:
                queryset = queryset.filter(is_public=True)
        
        return queryset.order_by('category', 'name')
    
    def perform_create(self, serializer):
        """Set organization and creator on create"""
        org = _get_request_organization(self.request)
        serializer.save(
            organization_id=getattr(org, 'id', None),
            created_by=self.request.user
        )
    
    def perform_destroy(self, instance):
        """Prevent deletion of system templates"""
        if instance.is_system:
            raise PermissionDenied("System templates cannot be deleted")
        super().perform_destroy(instance)
    
    @action(detail=True, methods=['post'])
    def apply_to_config(self, request, pk=None):
        """Apply template to a voucher mode config"""
        template = self.get_object()
        config_id = request.data.get('config_id')
        
        if not config_id:
            return Response(
                {'error': 'config_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            organization = _get_request_organization(request)
            if not organization:
                return Response(
                    {'error': 'Active organization required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            config = VoucherModeConfig.objects.get(
                config_id=config_id,
                organization=organization,
            )
            
            # Create new schema version with template
            last_version = VoucherSchema.objects.filter(
                voucher_mode_config=config
            ).aggregate(Max('version'))['version__max']
            
            new_schema = VoucherSchema.objects.create(
                voucher_mode_config=config,
                schema=template.schema,
                version=(last_version or 0) + 1,
                status=VoucherSchemaStatus.DRAFT,
                created_by=request.user,
                change_notes=f"Applied template: {template.name}"
            )
            
            # Increment usage count
            template.usage_count += 1
            template.save(update_fields=['usage_count'])
            
            return Response({
                'message': 'Template applied successfully',
                'schema': VoucherSchemaSerializer(new_schema).data
            })
        
        except VoucherModeConfig.DoesNotExist:
            return Response(
                {'error': 'Voucher mode config not found'},
                status=status.HTTP_404_NOT_FOUND
            )
