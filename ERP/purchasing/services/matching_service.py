"""
3-way match validation helpers for PO -> GR -> Invoice.
These utilities operate on lightweight dicts to avoid DB coupling.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Dict, Any


def _get_decimal(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def calculate_variance(
    po_qty: Decimal,
    gr_qty: Decimal,
    inv_qty: Decimal,
    po_unit_price: Decimal,
    inv_unit_price: Decimal,
) -> Dict[str, Decimal]:
    """Return quantity and price variances for a single PO line."""
    qty_variance_po_vs_gr = gr_qty - po_qty
    qty_variance_gr_vs_inv = inv_qty - gr_qty
    price_variance = inv_unit_price - po_unit_price
    return {
        "qty_variance_po_vs_gr": qty_variance_po_vs_gr,
        "qty_variance_gr_vs_inv": qty_variance_gr_vs_inv,
        "price_variance": price_variance,
    }


def validate_3way_match(
    po_lines: Iterable[Dict[str, Any]],
    gr_lines: Iterable[Dict[str, Any]],
    inv_lines: Iterable[Dict[str, Any]],
    qty_tolerance: Decimal = Decimal("0"),
    price_tolerance: Decimal = Decimal("0"),
) -> Dict[str, Any]:
    """
    Validate PO vs GR vs Invoice quantities and prices.

    Args:
        po_lines: iterable of dicts with keys: id, quantity_ordered, unit_price
        gr_lines: iterable of dicts with keys: po_line_id, quantity_received|quantity_accepted
        inv_lines: iterable of dicts with keys: po_line_id, quantity_invoiced, unit_price
        qty_tolerance: allowable quantity variance
        price_tolerance: allowable unit price variance

    Returns:
        dict with overall status (pass/warn/fail) and per-line variance details.
    """
    po_map = {line["id"]: line for line in po_lines}

    gr_map: Dict[int, Dict[str, Any]] = {}
    for line in gr_lines:
        key = line["po_line_id"]
        qty = _get_decimal(line.get("quantity_accepted", line.get("quantity_received", 0)))
        gr_map[key] = gr_map.get(key, {"qty": Decimal("0")})
        gr_map[key]["qty"] += qty

    inv_map: Dict[int, Dict[str, Any]] = {}
    for line in inv_lines:
        key = line["po_line_id"]
        qty = _get_decimal(line.get("quantity_invoiced", 0))
        inv_map[key] = inv_map.get(key, {"qty": Decimal("0"), "unit_price": _get_decimal(line.get("unit_price", 0))})
        inv_map[key]["qty"] += qty
        inv_map[key]["unit_price"] = _get_decimal(line.get("unit_price", inv_map[key]["unit_price"]))

    results = []
    overall_status = "pass"

    for po_id, po_line in po_map.items():
        po_qty = _get_decimal(po_line.get("quantity_ordered", 0))
        po_unit_price = _get_decimal(po_line.get("unit_price", 0))
        gr_qty = gr_map.get(po_id, {}).get("qty", Decimal("0"))
        inv_qty = inv_map.get(po_id, {}).get("qty", Decimal("0"))
        inv_unit_price = inv_map.get(po_id, {}).get("unit_price", po_unit_price)

        variances = calculate_variance(po_qty, gr_qty, inv_qty, po_unit_price, inv_unit_price)

        over_received = variances["qty_variance_po_vs_gr"] > qty_tolerance
        over_invoiced = variances["qty_variance_gr_vs_inv"] > qty_tolerance
        price_diff = variances["price_variance"].copy_abs() > price_tolerance

        line_status = "pass"
        if over_received or over_invoiced or price_diff:
            line_status = "fail"
        elif any(v != 0 for v in variances.values()):
            line_status = "warn"

        if line_status == "fail" and overall_status == "pass":
            overall_status = "fail"
        elif line_status == "warn" and overall_status == "pass":
            overall_status = "warn"

        results.append({
            "po_line_id": po_id,
            "po_qty": po_qty,
            "gr_qty": gr_qty,
            "inv_qty": inv_qty,
            "po_unit_price": po_unit_price,
            "inv_unit_price": inv_unit_price,
            "status": line_status,
            **variances,
            "over_received": over_received,
            "over_invoiced": over_invoiced,
            "price_out_of_tolerance": price_diff,
        })

    return {"status": overall_status, "lines": results}
