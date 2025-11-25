from rest_framework import serializers

from lpg_vertical.models import (
    ConversionRule,
    CylinderSKU,
    CylinderType,
    Dealer,
    InventoryMovement,
    LogisticsTrip,
    LpgProduct,
    NocPurchase,
    SalesInvoice,
    SalesInvoiceLine,
    TransportProvider,
    Vehicle,
)


class CylinderTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CylinderType
        fields = "__all__"
        read_only_fields = ("organization", "created_at", "updated_at")


class CylinderSKUSerializer(serializers.ModelSerializer):
    class Meta:
        model = CylinderSKU
        fields = "__all__"
        read_only_fields = ("organization", "created_at", "updated_at")


class ConversionRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConversionRule
        fields = "__all__"
        read_only_fields = ("organization", "created_at", "updated_at")


class DealerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dealer
        fields = "__all__"
        read_only_fields = ("organization", "created_at", "updated_at")


class TransportProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransportProvider
        fields = "__all__"
        read_only_fields = ("organization", "created_at", "updated_at")


class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = "__all__"
        read_only_fields = ("organization", "created_at", "updated_at")


class InventoryMovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryMovement
        fields = "__all__"
        read_only_fields = ("organization", "created_at", "updated_at")


class NocPurchaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = NocPurchase
        fields = "__all__"
        read_only_fields = (
            "organization",
            "created_at",
            "updated_at",
            "status",
            "posted_journal",
            "allocation_snapshot",
        )


class LpgProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = LpgProduct
        fields = "__all__"
        read_only_fields = ("organization", "created_at", "updated_at")


class SalesInvoiceLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalesInvoiceLine
        fields = (
            "id",
            "product",
            "cylinder_sku",
            "quantity",
            "rate",
            "discount",
            "tax_rate",
            "tax_amount",
            "line_total",
        )
        read_only_fields = ("tax_amount", "line_total")


class SalesInvoiceSerializer(serializers.ModelSerializer):
    lines = SalesInvoiceLineSerializer(many=True)

    class Meta:
        model = SalesInvoice
        fields = (
            "id",
            "organization",
            "date",
            "invoice_no",
            "dealer",
            "payment_type",
            "status",
            "empty_cylinders_collected",
            "notes",
            "posted_journal",
            "taxable_amount",
            "tax_amount",
            "total_amount",
            "lines",
        )
        read_only_fields = (
            "organization",
            "status",
            "posted_journal",
            "taxable_amount",
            "tax_amount",
            "total_amount",
        )

    def create(self, validated_data):
        lines_data = validated_data.pop("lines", [])
        invoice = SalesInvoice.objects.create(**validated_data)
        for line_data in lines_data:
            SalesInvoiceLine.objects.create(
                invoice=invoice,
                organization=invoice.organization,
                **line_data,
            )
        invoice.recompute_totals()
        invoice.save(update_fields=["taxable_amount", "tax_amount", "total_amount"])
        return invoice

    def update(self, instance, validated_data):
        lines_data = validated_data.pop("lines", [])
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.lines.all().delete()
        for line_data in lines_data:
            SalesInvoiceLine.objects.create(
                invoice=instance,
                organization=instance.organization,
                **line_data,
            )
        instance.recompute_totals()
        instance.save()
        return instance


class LogisticsTripSerializer(serializers.ModelSerializer):
    class Meta:
        model = LogisticsTrip
        fields = "__all__"
        read_only_fields = ("organization", "created_at", "updated_at", "status", "posted_journal")
