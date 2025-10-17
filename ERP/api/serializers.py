from decimal import Decimal
from typing import List
from rest_framework import serializers
from accounting.models import (
    ChartOfAccount,
    FiscalYear,
    Journal,
    JournalLine,
    CurrencyExchangeRate,
)


class ChartOfAccountSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField(read_only=True)
    class Meta:     
        model = ChartOfAccount
        fields = [
            "account_id",
            "organization",
            "parent_account",
            "account_type",
            "account_code",
            "account_name",
            "description",
            "is_active",
            "children",
        ]
        read_only_fields = ["account_code", "children"]

    def get_children(self, obj: ChartOfAccount) -> List[dict]:
        serializer = ChartOfAccountSerializer(
            obj.chartofaccount_set.all().select_related("account_type"),
            many=True,
            context=self.context,
        )
        return serializer.data

    def validate_parent_account(self, value: ChartOfAccount | None) -> ChartOfAccount | None:
        org = self.instance.organization if self.instance else self.context["request"].user.organization
        if value and value.organization != org:
            raise serializers.ValidationError("Parent account must belong to same organization")
        return value

class JournalLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = JournalLine
        fields = [
            "journal_line_id",
            "line_number",
            "account",
            "description",
            "debit_amount",
            "credit_amount",
            "currency_code",
            "exchange_rate",
            "functional_debit_amount",
            "functional_credit_amount",
            "department",
            "project",
            "cost_center",
            "tax_code",
            "memo",
        ]

class JournalSerializer(serializers.ModelSerializer):
    lines = JournalLineSerializer(many=True)

    class Meta:
        model = Journal
        fields = [
            "journal_id",
            "organization",
            "journal_number",
            "journal_type",
            "period",
            "journal_date",
            "reference",
            "description",
            "currency_code",
            "exchange_rate",
            "total_debit",
            "total_credit",
            "status",
            "lines",
        ]
        read_only_fields = ["journal_number", "status", "total_debit", "total_credit"]

    def validate(self, attrs):
        lines = attrs.get("lines", [])
        total_debit = sum(Decimal(str(l.get("debit_amount", 0))) for l in lines)
        total_credit = sum(Decimal(str(l.get("credit_amount", 0))) for l in lines)
        if total_debit != total_credit:
            raise serializers.ValidationError("Journal lines not balanced")
        attrs["total_debit"] = total_debit
        attrs["total_credit"] = total_credit
        return attrs

    def create(self, validated_data):
        lines_data = validated_data.pop("lines")
        journal = Journal.objects.create(**validated_data)
        for idx, line in enumerate(lines_data, start=1):
            JournalLine.objects.create(journal=journal, line_number=idx, **line)
        return journal

    def update(self, instance, validated_data):
        lines_data = validated_data.pop("lines", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if lines_data is not None:
            instance.lines.all().delete()
            for idx, line in enumerate(lines_data, start=1):
                JournalLine.objects.create(journal=instance, line_number=idx, **line)
        return instance

class CurrencyExchangeRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CurrencyExchangeRate
        fields = [
            "rate_id",
            "organization",
            "from_currency",
            "to_currency",
            "rate_date",
            "exchange_rate",
            "is_average_rate",
            "source",
        ]

class FiscalYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = FiscalYear
        fields = [
            'fiscal_year_id',
            'organization',
            'code',
            'name',
            'start_date',
            'end_date',
            'status',
            'is_current',
        ]