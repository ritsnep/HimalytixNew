"""
Service layer for LPG vertical.

This file is intentionally thin and integration-focused. You are expected to
wire these functions into your existing inventory and accounting engines.

Think of these as orchestration helpers:
  - they read lpg_vertical models
  - they call INTO your core ERP (vouchers, GL, stock movement)
"""

from decimal import Decimal
from typing import Dict

from .models import NocPurchase, CylinderType, ConversionRule, LogisticsTrip


def allocate_mt_to_cylinders(quantity_mt: Decimal) -> Dict[CylinderType, int]:
    """
    Example allocation helper that converts bulk LPG in MT into cylinder counts,
    based on ConversionRule.

    This returns a dict {CylinderType: cylinder_count}.

    IMPORTANT:
        This is a simple illustration. In your real implementation you may need
        per-company rules, rounding, prioritization, etc.
    """
    allocations: Dict[CylinderType, int] = {}

    rules = ConversionRule.objects.filter(is_default=True).select_related("cylinder_type")
    if not rules.exists():
        return allocations

    remaining_mt = Decimal(quantity_mt)

    for rule in rules:
        if rule.mt_per_cylinder <= 0:
            continue

        possible_count = int(remaining_mt / rule.mt_per_cylinder)
        if possible_count <= 0:
            continue

        allocations[rule.cylinder_type] = possible_count
        remaining_mt -= rule.mt_per_cylinder * possible_count

    return allocations


def post_noc_purchase(noc_purchase: NocPurchase) -> None:
    """
    Hook point for integrating NOC purchase with:
      - your purchasing/voucher module
      - your accounting/GL module
      - your inventory/stock module

    Suggested steps inside your project:
      1. Create a Purchase Voucher in your existing table with:
         - vendor = NOC
         - lines = LPG bulk, freight, tax
      2. Post corresponding GL entries (DR inventory/tax/freight, CR NOC A/P).
      3. Use `allocate_mt_to_cylinders` to decide cylinder allocation and call
         your inventory service to add stock.
      4. Mark `noc_purchase.status = POSTED`.

    This function is intentionally left as a stub with comments so you can
    safely adapt it to your exact DB schema.

    Example pseudo-code (to be implemented in your project):

        from accounting.services import create_purchase_voucher
        from inventory.services import add_bulk_lpg_stock

        voucher = create_purchase_voucher(...)
        add_bulk_lpg_stock(...)
        noc_purchase.base_purchase = voucher
        noc_purchase.status = NocPurchase.STATUS_POSTED
        noc_purchase.save()
    """
    # TODO: Implement integration here using your existing ERP services.
    raise NotImplementedError("Implement posting logic in your project")


def post_logistics_trip(trip: LogisticsTrip) -> None:
    """
    Hook point for integrating a logistics trip with:
      - your inventory transfer logic (from_location -> to_location)
      - your cost accounting (freight/logistics expense)

    Example steps:
      1. Call inventory.transfer_cylinders(from_location, to_location, trip.cylinder_count)
      2. Create a GL/Expense entry for `trip.cost` under Logistics Expense.
    """
    # TODO: Implement integration here using your existing ERP services.
    raise NotImplementedError("Implement logistics posting logic in your project")
