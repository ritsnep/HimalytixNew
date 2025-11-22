from __future__ import annotations

from django.db import transaction
from rest_framework import serializers

from .models import CreditDebitNote, InvoiceHeader, InvoiceLine
from .utils import compute_vat_and_total


class InvoiceLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLine
        fields = [
            "id",
            "description",
            "quantity",
            "unit_price",
            "vat_rate",
            "taxable_amount",
            "vat_amount",
            "line_total",
        ]
        read_only_fields = ["taxable_amount", "vat_amount", "line_total"]

    def create(self, validated_data):
        line = InvoiceLine(**validated_data)
        line.save()
        return line


class InvoiceHeaderSerializer(serializers.ModelSerializer):
    lines = InvoiceLineSerializer(many=True, write_only=True)

    class Meta:
        model = InvoiceHeader
        fields = [
            "id",
            "tenant",
            "invoice_number",
            "fiscal_year",
            "invoice_date",
            "customer_name",
            "customer_pan",
            "customer_vat",
            "billing_address",
            "payment_method",
            "taxable_amount",
            "vat_amount",
            "total_amount",
            "sync_status",
            "canceled",
            "canceled_reason",
            "lines",
        ]
        read_only_fields = [
            "invoice_number",
            "taxable_amount",
            "vat_amount",
            "total_amount",
            "sync_status",
            "canceled",
        ]

    def create(self, validated_data):
        lines_data = validated_data.pop("lines", [])
        with transaction.atomic():
            invoice = InvoiceHeader.objects.create(**validated_data)
            for line_data in lines_data:
                InvoiceLine.objects.create(invoice=invoice, **line_data)
            invoice._allow_update = True  # recompute totals after line creation
            invoice._compute_totals()
            invoice.save(update_fields=["taxable_amount", "vat_amount", "total_amount", "updated_at"])
        return invoice


class CreditDebitNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditDebitNote
        fields = ["id", "invoice", "note_type", "reason", "amount", "taxable_amount", "vat_amount", "created_at"]
        read_only_fields = ["created_at"]
