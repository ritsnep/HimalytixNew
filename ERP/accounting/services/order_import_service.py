from typing import List
from decimal import Decimal

def import_purchase_order_lines(organization, order_id) -> List[dict]:
    """Return list of line dicts for a given purchase order id.

    Assumptions:
    - Purchase orders live in `purchasing` app as `PurchaseOrder` and `PurchaseOrderLine`.
    - Lines contain `quantity`, `unit_cost`, `unit`, `warehouse`/`godown`, and `id`.
    """
    try:
        from purchasing.models import PurchaseOrder, PurchaseOrderLine
    except Exception:
        return []

    try:
        po = PurchaseOrder.objects.get(pk=order_id, organization=organization)
    except PurchaseOrder.DoesNotExist:
        return []

    lines = []
    qs = PurchaseOrderLine.objects.filter(purchase_order=po).order_by('line_number')
    for l in qs:
        lines.append({
            'description': getattr(l, 'description', '') or '',
            'quantity': getattr(l, 'quantity', 0) or 0,
            'unit_cost': getattr(l, 'unit_cost', 0) or 0,
            'unit': getattr(l, 'unit', None),
            'godown': getattr(l, 'warehouse', None) or getattr(l, 'godown', None),
            'po_line_id': getattr(l, 'pk', None),
            'po_reference': getattr(po, 'pk', None),
        })
    return lines
