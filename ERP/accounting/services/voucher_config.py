"""
Voucher Configuration Resolver Service

Provides runtime configuration of voucher fields with organization-specific overrides.
"""

from typing import Dict, List, Any, Optional
from django.core.cache import cache
from accounting.models import VoucherType, ConfigurableField, FieldConfig


class VoucherConfigResolver:
    """
    Service class to resolve voucher field configurations with organization overrides.
    """

    def __init__(self, organization, voucher_type: VoucherType):
        """
        Initialize resolver for a specific organization and voucher type.

        Args:
            organization: Organization instance
            voucher_type: VoucherType instance
        """
        self.organization = organization
        self.voucher_type = voucher_type
        self.cache_key = f"voucher_config_{organization.id}_{voucher_type.id}"

    def get_fields_config(self, use_cache: bool = True) -> Dict[str, Any]:
        """
        Get the effective field configuration for this organization and voucher type.

        Args:
            use_cache: Whether to use cached results

        Returns:
            Dict containing voucher_type and fields list
        """
        if use_cache:
            cached = cache.get(self.cache_key)
            if cached:
                return cached

        # Get all fields for this voucher type
        fields = ConfigurableField.objects.filter(
            voucher_type=self.voucher_type
        ).order_by('field_order', 'name')

        config_list = []
        for field in fields:
            # Look for an override for this org+field
            override = FieldConfig.objects.filter(
                organization=self.organization,
                field=field
            ).first()

            # Merge defaults with overrides
            field_config = {
                'id': field.id,
                'name': field.name,
                'label': override.label_override if override and override.label_override else field.default_label,
                # Keep the field label/name in the tooltip until richer copy is supplied.
                'tooltip': (
                    override.tooltip_override if override and override.tooltip_override else
                    field.default_tooltip or
                    field.default_label or
                    field.name
                ),
                'data_type': override.data_type_override if override and override.data_type_override else field.default_data_type,
                'visible': override.visible if override and override.visible is not None else field.default_visible,
                'mandatory': override.mandatory if override and override.mandatory is not None else field.default_mandatory,
                'placeholder': override.placeholder_override if override and override.placeholder_override else field.default_placeholder,
                'field_order': field.field_order,
            }
            config_list.append(field_config)

        result = {
            'voucher_type': {
                'id': self.voucher_type.id,
                'name': self.voucher_type.name,
                'code': self.voucher_type.code,
                'description': self.voucher_type.description,
            },
            'fields': config_list
        }

        # Cache for 1 hour
        if use_cache:
            cache.set(self.cache_key, result, 3600)

        return result

    def get_visible_fields(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        Get only visible fields for this configuration.

        Args:
            use_cache: Whether to use cached results

        Returns:
            List of visible field configurations
        """
        config = self.get_fields_config(use_cache)
        return [field for field in config['fields'] if field['visible']]

    def invalidate_cache(self):
        """Invalidate the cache for this configuration."""
        cache.delete(self.cache_key)

    @classmethod
    def invalidate_all_cache(cls):
        """Invalidate all voucher configuration caches."""
        # This is a simple implementation - in production you might want
        # a more sophisticated cache invalidation strategy
        cache.delete_pattern("voucher_config_*")


class VoucherConfigManager:
    """
    Manager class for voucher configurations across the system.
    """

    @staticmethod
    def get_voucher_types(active_only: bool = True) -> List[VoucherType]:
        """
        Get all voucher types.

        Args:
            active_only: Whether to return only active voucher types

        Returns:
            List of VoucherType instances
        """
        queryset = VoucherType.objects.all()
        if active_only:
            queryset = queryset.filter(is_active=True)
        return list(queryset.order_by('name'))

    @staticmethod
    def get_config_resolver(organization, voucher_type_code: str) -> Optional[VoucherConfigResolver]:
        """
        Get a config resolver for a voucher type by code.

        Args:
            organization: Organization instance
            voucher_type_code: Voucher type code (e.g., 'journal', 'payment')

        Returns:
            VoucherConfigResolver instance or None if voucher type not found
        """
        try:
            voucher_type = VoucherType.objects.get(code=voucher_type_code, is_active=True)
            return VoucherConfigResolver(organization, voucher_type)
        except VoucherType.DoesNotExist:
            return None

    @staticmethod
    def create_default_voucher_types():
        """
        Create default voucher types if they don't exist.
        This is useful for initial setup.
        """
        defaults = [
            {
                'name': 'Journal Entry',
                'code': 'journal',
                'description': 'General journal entries for accounting transactions',
            },
            {
                'name': 'Payment Voucher',
                'code': 'payment',
                'description': 'Payment vouchers for outgoing payments',
            },
            {
                'name': 'Receipt Voucher',
                'code': 'receipt',
                'description': 'Receipt vouchers for incoming payments',
            },
            {
                'name': 'Sales Invoice',
                'code': 'sales',
                'description': 'Sales invoice vouchers',
            },
            {
                'name': 'Purchase Invoice',
                'code': 'purchase',
                'description': 'Purchase invoice vouchers',
            },
        ]

        for default in defaults:
            VoucherType.objects.get_or_create(
                code=default['code'],
                defaults={
                    'name': default['name'],
                    'description': default['description'],
                    'is_active': True,
                }
            )

    @staticmethod
    def create_default_fields_for_voucher_type(voucher_type: VoucherType):
        """
        Create default fields for a voucher type.
        This sets up the basic fields that most vouchers need.
        """
        # Common fields for all voucher types
        common_fields = [
            {
                'name': 'date',
                'default_label': 'Date',
                'default_data_type': 'date',
                'default_visible': True,
                'default_mandatory': True,
                'field_order': 1,
            },
            {
                'name': 'reference',
                'default_label': 'Reference',
                'default_data_type': 'text',
                'default_visible': True,
                'default_mandatory': False,
                'field_order': 2,
            },
            {
                'name': 'description',
                'default_label': 'Description',
                'default_data_type': 'textarea',
                'default_visible': True,
                'default_mandatory': False,
                'field_order': 3,
            },
        ]

        # Journal-specific fields
        if voucher_type.code == 'journal':
            journal_fields = [
                {
                    'name': 'account',
                    'default_label': 'Account',
                    'default_data_type': 'text',
                    'default_visible': True,
                    'default_mandatory': True,
                    'field_order': 4,
                },
                {
                    'name': 'debit_amount',
                    'default_label': 'Debit Amount',
                    'default_data_type': 'decimal',
                    'default_visible': True,
                    'default_mandatory': False,
                    'field_order': 5,
                },
                {
                    'name': 'credit_amount',
                    'default_label': 'Credit Amount',
                    'default_data_type': 'decimal',
                    'default_visible': True,
                    'default_mandatory': False,
                    'field_order': 6,
                },
            ]
            common_fields.extend(journal_fields)

        # Create the fields
        for field_data in common_fields:
            ConfigurableField.objects.get_or_create(
                voucher_type=voucher_type,
                name=field_data['name'],
                defaults=field_data
            )