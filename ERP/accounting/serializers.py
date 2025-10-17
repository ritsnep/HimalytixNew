from rest_framework import serializers
from .models import VoucherModeConfig
from .models import Journal

class JournalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Journal
        fields = '__all__'

class VoucherModeConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoucherModeConfig
        fields = [
            'journal_type',
            'layout_style',
            'show_account_balances',
            'show_tax_details',
            'show_dimensions',
            'allow_multiple_currencies',
            'require_line_description',
        ]