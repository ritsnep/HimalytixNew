from decimal import Decimal
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from accounting.models import (
    APPayment,
    ARReceipt,
    Asset,
    BankAccount,
    Customer,
    IntegrationEvent,
    PurchaseInvoice,
    SalesInvoice,
    Vendor,
)

from accounting.models import JournalLine, Journal, VoucherLine, VoucherType, ConfigurableField, FieldConfig


class JournalLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = JournalLine
        fields = [
            'journal_line_id', 'journal', 'line_number', 'account', 'description',
            'debit_amount', 'credit_amount', 'department', 'project', 'cost_center',
            'tax_code', 'memo', 'udf_data', 'created_at', 'created_by'
        ]
        read_only_fields = ['journal_line_id', 'created_at', 'created_by']


class VoucherLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoucherLine
        fields = [
            'voucher_line_id', 'journal', 'line_number', 'account', 'description',
            'debit_amount', 'credit_amount', 'department', 'project', 'cost_center',
            'tax_code', 'tax_rate', 'tax_amount', 'memo', 'udf_data', 'created_at', 'created_by'
        ]
        read_only_fields = ['voucher_line_id', 'created_at', 'created_by']


class VoucherTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoucherType
        fields = ['id', 'name', 'code', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ConfigurableFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfigurableField
        fields = [
            'id', 'voucher_type', 'name', 'default_label', 'default_tooltip',
            'default_data_type', 'default_visible', 'default_mandatory',
            'default_placeholder', 'field_order', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class FieldConfigSerializer(serializers.ModelSerializer):
    field_name = serializers.CharField(source='field.name', read_only=True)
    voucher_type_name = serializers.CharField(source='field.voucher_type.name', read_only=True)

    class Meta:
        model = FieldConfig
        fields = [
            'id', 'organization', 'field', 'field_name', 'voucher_type_name',
            'label_override', 'tooltip_override', 'data_type_override',
            'visible', 'mandatory', 'placeholder_override', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class VendorSerializer(serializers.ModelSerializer):
    ap_outstanding_balance = serializers.DecimalField(max_digits=19, decimal_places=4, read_only=True)
    available_credit = serializers.SerializerMethodField()

    def get_available_credit(self, obj: Vendor):
        if obj.credit_limit is None:
            return None
        bal = obj.ap_outstanding_balance or Decimal("0.00")
        return (obj.credit_limit - bal).quantize(Decimal("0.01"))

    class Meta:
        model = Vendor
        fields = [
            'vendor_id',
            'code',
            'display_name',
            'status',
            'payment_term',
            'accounts_payable_account',
            'credit_limit',
            'ap_outstanding_balance',
            'available_credit',
            'on_hold',
            'default_currency',
        ]


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['customer_id', 'code', 'display_name', 'status', 'payment_term', 'accounts_receivable_account']


class PurchaseInvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseInvoice
        fields = ['invoice_id', 'invoice_number', 'vendor', 'invoice_date', 'due_date', 'total', 'status']


class AccountingSalesInvoiceSerializer(serializers.ModelSerializer):
    """Serializer for accounting module SalesInvoice (distinct from lpg_vertical.SalesInvoiceSerializer)."""
    class Meta:
        model = SalesInvoice
        fields = ['invoice_id', 'invoice_number', 'customer', 'invoice_date', 'due_date', 'total', 'status']


# Alias for backward compatibility
SalesInvoiceSerializer = AccountingSalesInvoiceSerializer


class APPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = APPayment
        fields = ['payment_id', 'payment_number', 'vendor', 'payment_date', 'payment_method', 'amount', 'status']


class ARReceiptSerializer(serializers.ModelSerializer):
    class Meta:
        model = ARReceipt
        fields = ['receipt_id', 'receipt_number', 'customer', 'receipt_date', 'amount']


class BankAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankAccount
        fields = ['account_id', 'bank_name', 'account_number', 'current_balance', 'currency']


class AssetSerializer(serializers.ModelSerializer):
    book_value = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = ['asset_id', 'name', 'category', 'acquisition_date', 'cost', 'book_value', 'status']

    @extend_schema_field({'type': 'string', 'format': 'decimal'})
    def get_book_value(self, obj: Asset) -> Decimal:
        # Simple book value: cost - accumulated_depreciation (can be extended)
        return (obj.cost or 0) - (obj.accumulated_depreciation or 0)


class IntegrationEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegrationEvent
        fields = ['event_id', 'event_type', 'payload', 'source_object', 'source_id', 'created_at']
