"""
Currency Bulk Import and Demo Template Views
Example implementation of universal bulk import system
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator

from accounting.models import Currency
from accounting.bulk_import.bulk_import_mixin import UniversalBulkImportView, UniversalDemoImportView
from accounting.views.views_mixins import PermissionRequiredMixin
from utils.htmx import require_htmx


class CurrencyBulkCreateView(PermissionRequiredMixin, LoginRequiredMixin, UniversalBulkImportView):
    """Handle bulk import of currencies from pasted data or CSV"""
    
    model = Currency
    permission_required = ('accounting', 'currency', 'add')
    
    # Define fields in order for parsing (tab/comma separated data)
    bulk_fields = ['currency_code', 'currency_name', 'symbol', 'is_active']
    
    # Detailed field configuration
    bulk_field_config = {
        'currency_code': {
            'required': True,
            'type': 'str',
            'unique_field': True,  # Check for duplicates
            'help_text': '3-letter ISO currency code (e.g., USD, EUR, INR)',
        },
        'currency_name': {
            'required': True,
            'type': 'str',
            'help_text': 'Full currency name (e.g., US Dollar)',
        },
        'symbol': {
            'required': False,
            'type': 'str',
            'help_text': 'Currency symbol (e.g., $, €, ₹)',
        },
        'is_active': {
            'required': False,
            'type': 'bool',
            'help_text': 'Whether currency is active (true/false)',
        },
    }
    
    auto_fields = ['created_by', 'updated_by']  # Don't include in bulk import
    
    def get_organization(self):
        """Get current user's organization"""
        return self.request.user.get_active_organization()
    
    @method_decorator(require_htmx)
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class CurrencyDemoImportView(PermissionRequiredMixin, LoginRequiredMixin, UniversalDemoImportView):
    """Import pre-configured demo currency templates"""
    
    model = Currency
    permission_required = ('accounting', 'currency', 'add')
    
    # Define demo templates
    demo_templates = {
        'major-currencies': [
            {'currency_code': 'USD', 'currency_name': 'US Dollar', 'symbol': '$', 'is_active': True},
            {'currency_code': 'EUR', 'currency_name': 'Euro', 'symbol': '€', 'is_active': True},
            {'currency_code': 'GBP', 'currency_name': 'British Pound', 'symbol': '£', 'is_active': True},
            {'currency_code': 'JPY', 'currency_name': 'Japanese Yen', 'symbol': '¥', 'is_active': True},
            {'currency_code': 'CHF', 'currency_name': 'Swiss Franc', 'symbol': 'CHF', 'is_active': True},
        ],
        'asian-currencies': [
            {'currency_code': 'INR', 'currency_name': 'Indian Rupee', 'symbol': '₹', 'is_active': True},
            {'currency_code': 'CNY', 'currency_name': 'Chinese Yuan', 'symbol': '¥', 'is_active': True},
            {'currency_code': 'SGD', 'currency_name': 'Singapore Dollar', 'symbol': 'S$', 'is_active': True},
            {'currency_code': 'HKD', 'currency_name': 'Hong Kong Dollar', 'symbol': 'HK$', 'is_active': True},
            {'currency_code': 'KRW', 'currency_name': 'South Korean Won', 'symbol': '₩', 'is_active': True},
            {'currency_code': 'THB', 'currency_name': 'Thai Baht', 'symbol': '฿', 'is_active': True},
        ],
        'all-common': [
            {'currency_code': 'USD', 'currency_name': 'US Dollar', 'symbol': '$', 'is_active': True},
            {'currency_code': 'EUR', 'currency_name': 'Euro', 'symbol': '€', 'is_active': True},
            {'currency_code': 'GBP', 'currency_name': 'British Pound', 'symbol': '£', 'is_active': True},
            {'currency_code': 'JPY', 'currency_name': 'Japanese Yen', 'symbol': '¥', 'is_active': True},
            {'currency_code': 'INR', 'currency_name': 'Indian Rupee', 'symbol': '₹', 'is_active': True},
            {'currency_code': 'CNY', 'currency_name': 'Chinese Yuan', 'symbol': '¥', 'is_active': True},
            {'currency_code': 'AUD', 'currency_name': 'Australian Dollar', 'symbol': 'A$', 'is_active': True},
            {'currency_code': 'CAD', 'currency_name': 'Canadian Dollar', 'symbol': 'C$', 'is_active': True},
            {'currency_code': 'CHF', 'currency_name': 'Swiss Franc', 'symbol': 'CHF', 'is_active': True},
            {'currency_code': 'SEK', 'currency_name': 'Swedish Krona', 'symbol': 'kr', 'is_active': True},
        ],
    }
    
    # Template metadata for better UI
    template_metadata = {
        'major-currencies': {
            'name': 'Major World Currencies',
            'description': 'Most commonly used currencies in international trade (USD, EUR, GBP, JPY, CHF)',
            'icon': 'bx-world',
        },
        'asian-currencies': {
            'name': 'Asian Currencies',
            'description': 'Common currencies used in Asian markets (INR, CNY, SGD, HKD, KRW, THB)',
            'icon': 'bx-map',
        },
        'all-common': {
            'name': 'All Common Currencies',
            'description': 'Comprehensive set of 10 most traded currencies worldwide',
            'icon': 'bx-globe',
        },
    }
    
    def get_organization(self):
        """Get current user's organization"""
        return self.request.user.get_active_organization()
    
    @method_decorator(require_htmx)
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
    
    @method_decorator(require_htmx)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
