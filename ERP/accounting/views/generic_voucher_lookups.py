import logging

from django.http import JsonResponse

from accounting.views.base_voucher_view import BaseVoucherView

logger = logging.getLogger(__name__)


class GenericVoucherVendorLookupJsonView(BaseVoucherView):
    def get(self, request, *args, **kwargs):
        organization = self.get_organization()
        query = request.GET.get('q', '').strip()
        limit = int(request.GET.get('limit', 10))

        from accounting.models import Vendor

        vendors = Vendor.objects.filter(organization=organization)
        if hasattr(Vendor, 'is_active'):
            vendors = vendors.filter(is_active=True)

        if query:
            vendors = vendors.filter(display_name__icontains=query) | vendors.filter(code__icontains=query)

        vendors = vendors.order_by('display_name')[:limit]

        results = []
        for v in vendors:
            vid = getattr(v, 'vendor_id', None) or getattr(v, 'id', None)
            code = getattr(v, 'code', '')
            name = getattr(v, 'display_name', '') or getattr(v, 'name', '')
            results.append({
                'id': vid,
                'text': f"{code} - {name}".strip(' -'),
                'code': code,
                'name': name,
            })

        return JsonResponse({'results': results, 'total': len(results)})


class GenericVoucherCustomerLookupJsonView(BaseVoucherView):
    def get(self, request, *args, **kwargs):
        organization = self.get_organization()
        query = request.GET.get('q', '').strip()
        limit = int(request.GET.get('limit', 10))

        from accounting.models import Customer

        customers = Customer.objects.filter(organization=organization)
        if hasattr(Customer, 'is_active'):
            customers = customers.filter(is_active=True)

        if query:
            customers = customers.filter(display_name__icontains=query) | customers.filter(code__icontains=query)

        customers = customers.order_by('display_name')[:limit]

        results = []
        for c in customers:
            cid = getattr(c, 'customer_id', None) or getattr(c, 'id', None)
            code = getattr(c, 'code', '')
            name = getattr(c, 'display_name', '') or getattr(c, 'name', '')
            results.append({
                'id': cid,
                'text': f"{code} - {name}".strip(' -'),
                'code': code,
                'name': name,
            })

        return JsonResponse({'results': results, 'total': len(results)})


class GenericVoucherProductLookupJsonView(BaseVoucherView):
    def get(self, request, *args, **kwargs):
        organization = self.get_organization()
        query = request.GET.get('q', '').strip()
        limit = int(request.GET.get('limit', 10))

        try:
            from inventory.models import Product
        except Exception:
            return JsonResponse({'results': [], 'total': 0})

        products = Product.objects.filter(organization=organization)
        if hasattr(Product, 'is_active'):
            products = products.filter(is_active=True)

        if query:
            products = (
                products.filter(code__icontains=query)
                | products.filter(name__icontains=query)
                | products.filter(barcode__icontains=query)
            )

        products = products.order_by('code')[:limit]

        results = []
        for p in products:
            pid = getattr(p, 'id', None)
            results.append({
                'id': pid,
                'text': f"{p.code} - {p.name}",
                'code': p.code,
                'name': p.name,
            })

        return JsonResponse({'results': results, 'total': len(results)})
