"""Debug views for typeahead configuration troubleshooting."""

from django.http import JsonResponse
from django.views import View


class TypeaheadDebugView(View):
    """
    Returns JSON with all configured typeahead endpoints and lookup mappings.
    Useful for debugging typeahead initialization issues.
    """
    
    def get(self, request):
        """Return configuration mapping for all voucher types."""
        
        endpoint_mapping = {
            'JOURNAL': {
                'account': '/accounting/vouchers/htmx/account-lookup/',
                'journal': '/accounting/journal-entry/lookup/journals/',
                'agent': '/accounting/journal-entry/lookup/agents/',
                'warehouse': '/accounting/journal-entry/lookup/warehouses/',
                'tax_code': '/accounting/journal-entry/lookup/tax-codes/',
                'cost_center': '/accounting/journal-entry/lookup/cost-centers/',
            },
            'SALES_INVOICE': {
                'customer': '/accounting/generic-voucher/htmx/customer-lookup/',
                'product': '/accounting/generic-voucher/htmx/product-lookup/',
                'tax_code': '/accounting/journal-entry/lookup/tax-codes/',
                'warehouse': '/accounting/journal-entry/lookup/warehouses/',
                'account': '/accounting/vouchers/htmx/account-lookup/',
            },
            'PURCHASE_INVOICE': {
                'vendor': '/accounting/generic-voucher/htmx/vendor-lookup/',
                'product': '/accounting/generic-voucher/htmx/product-lookup/',
                'tax_code': '/accounting/journal-entry/lookup/tax-codes/',
                'warehouse': '/accounting/journal-entry/lookup/warehouses/',
                'account': '/accounting/vouchers/htmx/account-lookup/',
            },
            'GOODS_RECEIPT': {
                'vendor': '/accounting/generic-voucher/htmx/vendor-lookup/',
                'product': '/accounting/generic-voucher/htmx/product-lookup/',
                'warehouse': '/accounting/journal-entry/lookup/warehouses/',
                'account': '/accounting/vouchers/htmx/account-lookup/',
            },
        }
        
        return JsonResponse({
            'status': 'debug',
            'endpoints': endpoint_mapping,
            'message': 'All configured typeahead endpoints for voucher entry forms',
        })
