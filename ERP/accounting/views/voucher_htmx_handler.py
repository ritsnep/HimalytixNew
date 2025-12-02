"""
Dispatcher for simple voucher HTMX actions used by base_voucher.html.

This thin wrapper keeps backward compatibility with the original
`journal_htmx` URL while delegating to the concrete HTMX handlers
implemented for Phase 2.
"""

from django.http import HttpResponseBadRequest
from django.views import View

from accounting.views.voucher_create_view import (
    VoucherCreateHtmxView,
    VoucherAccountLookupHtmxView,
    VoucherTaxCalculationHtmxView,
)


class VoucherHtmxHandler(View):
    """Route HTMX actions to their dedicated handler views."""

    action_map = {
        'add_line': VoucherCreateHtmxView,
        'account_lookup': VoucherAccountLookupHtmxView,
        'tax_calc': VoucherTaxCalculationHtmxView,
    }

    def dispatch(self, request, *args, **kwargs):
        action = kwargs.get('action')
        view_cls = self.action_map.get(action)
        if not view_cls:
            return HttpResponseBadRequest(f"Unknown HTMX action: {action}")
        return view_cls.as_view()(request, *args, **kwargs)
