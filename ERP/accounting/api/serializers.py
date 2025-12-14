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

from accounting.models import JournalLine, Journal


class JournalLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = JournalLine
        fields = [
            'journal_line_id', 'journal', 'line_number', 'account', 'description',
            'debit_amount', 'credit_amount', 'department', 'project', 'cost_center',
            'tax_code', 'memo', 'udf_data', 'created_at', 'created_by'
        ]
        read_only_fields = ['journal_line_id', 'created_at', 'created_by']


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = ['vendor_id', 'code', 'display_name', 'status', 'payment_term', 'accounts_payable_account']


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
