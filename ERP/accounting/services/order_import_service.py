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
    # Preserve authoring order without assuming a non-existent `line_number` field.
    # Ordering by PK keeps the original creation sequence and avoids FieldError.
    qs = PurchaseOrderLine.objects.filter(purchase_order=po).order_by('id')
    for l in qs:
        product = getattr(l, 'product', None)
        lines.append({
            'description': getattr(l, 'description', '') or '',
            'quantity': getattr(l, 'quantity', getattr(l, 'quantity_ordered', 0)) or 0,
            'unit_cost': getattr(l, 'unit_cost', getattr(l, 'unit_price', 0)) or 0,
            'unit': getattr(l, 'unit', None),
            'godown': getattr(l, 'warehouse', None) or getattr(l, 'godown', None) or getattr(l, 'warehouse_id', None) or getattr(l, 'godown_id', None),
            'po_line_id': getattr(l, 'pk', None),
            'po_reference': getattr(po, 'pk', None),
            'product_id': getattr(product, 'pk', None),
            'product_code': getattr(product, 'product_code', None) or getattr(product, 'code', None),
            'account_id': getattr(l, 'expense_account_id', None) or getattr(l, 'inventory_account_id', None),
            'vat_rate': getattr(l, 'vat_rate', None),
        })
    return lines
