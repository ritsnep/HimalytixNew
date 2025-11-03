"""
API serializers for Forms Designer
"""
from rest_framework import serializers
from accounting.models import VoucherModeConfig, VoucherUDFConfig
from .models import VoucherSchema, SchemaTemplate, VoucherSchemaStatus


class VoucherUDFConfigSerializer(serializers.ModelSerializer):
    """Serializer for UDF configuration"""
    
    class Meta:
        model = VoucherUDFConfig
        fields = [
            'udf_id', 'organization', 'voucher_mode', 'field_name', 'display_name',
            'field_type', 'scope', 'is_required', 'is_active', 'default_value',
            'is_conditional', 'condition_json', 'choices', 'min_value', 'max_value',
            'min_length', 'max_length', 'validation_regex', 'help_text', 'display_order',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['udf_id', 'created_at', 'updated_at']
    
    def validate_field_name(self, value):
        """Ensure field name follows naming convention"""
        import re
        if not re.match(r'^[a-z][a-z0-9_]*$', value):
            raise serializers.ValidationError(
                "Field name must start with a letter and contain only lowercase letters, numbers, and underscores."
            )
        return value
    
    def validate(self, data):
        """Cross-field validation"""
        # Validate choices for select fields
        if data.get('field_type') in ['select', 'multiselect']:
            if not data.get('choices'):
                raise serializers.ValidationError({
                    'choices': "Choices are required for select and multiselect fields."
                })
        
        # Validate numeric constraints
        if data.get('field_type') in ['number', 'decimal']:
            min_val = data.get('min_value')
            max_val = data.get('max_value')
            if min_val is not None and max_val is not None and min_val > max_val:
                raise serializers.ValidationError({
                    'min_value': "Minimum value cannot be greater than maximum value."
                })
        
        return data


class VoucherSchemaSerializer(serializers.ModelSerializer):
    """Serializer for voucher schema with workflow support"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, allow_null=True)
    updated_by_name = serializers.CharField(source='updated_by.get_full_name', read_only=True, allow_null=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True, allow_null=True)
    
    class Meta:
        model = VoucherSchema
        fields = [
            'id', 'voucher_mode_config', 'schema', 'version', 'status', 'status_display',
            'is_active', 'created_at', 'created_by', 'created_by_name', 'updated_at',
            'updated_by', 'updated_by_name', 'submitted_at', 'submitted_by', 'approved_at',
            'approved_by', 'approved_by_name', 'rejected_at', 'rejected_by', 'rejection_reason',
            'published_at', 'published_by', 'change_notes'
        ]
        read_only_fields = [
            'id', 'version', 'created_at', 'submitted_at', 'approved_at',
            'rejected_at', 'published_at'
        ]
    
    def validate_schema(self, value):
        """Validate schema structure"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Schema must be a valid JSON object")
        
        required_keys = ['header', 'lines']
        for key in required_keys:
            if key not in value:
                raise serializers.ValidationError(f"Schema must contain '{key}' key")
        
        return value


class SchemaTemplateSerializer(serializers.ModelSerializer):
    """Serializer for schema templates"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, allow_null=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    
    class Meta:
        model = SchemaTemplate
        fields = [
            'template_id', 'name', 'description', 'category', 'category_display',
            'schema', 'is_system', 'is_public', 'organization_id', 'created_at',
            'created_by', 'created_by_name', 'usage_count'
        ]
        read_only_fields = ['template_id', 'created_at', 'usage_count', 'is_system']
    
    def validate_schema(self, value):
        """Validate template schema structure"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Schema must be a valid JSON object")
        return value


class VoucherModeConfigListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for voucher config list"""
    active_schema_count = serializers.SerializerMethodField()
    draft_schema_count = serializers.SerializerMethodField()
    
    class Meta:
        model = VoucherModeConfig
        fields = [
            'config_id', 'code', 'name', 'description', 'is_default',
            'layout_style', 'is_active', 'active_schema_count', 'draft_schema_count'
        ]
    
    def get_active_schema_count(self, obj):
        return obj.schemas.filter(is_active=True).count()
    
    def get_draft_schema_count(self, obj):
        return obj.schemas.filter(status=VoucherSchemaStatus.DRAFT).count()
