from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Optional, Tuple

from django.core.exceptions import ValidationError
from django.db import models, transaction

from accounting.models import SalesInvoice, SalesOrder, SalesOrderLine
from accounting.services.sales_invoice_service import SalesInvoiceService
from inventory.models import InventoryItem, Product, Warehouse


class SalesOrderService:
    """Business operations for sales orders: creation, status changes, and invoicing."""

    ALLOWED_TRANSITIONS = {
        "draft": {"confirmed", "cancelled"},
        "confirmed": {"fulfilled", "cancelled"},
        "fulfilled": {"invoiced"},
        "invoiced": set(),
        "cancelled": set(),
    }

    def __init__(self, user):
        self.user = user

    def _validate_line_payload(self, lines: Iterable[dict]) -> list[dict]:
        prepared: list[dict] = []
        for index, line in enumerate(lines, start=1):
            description = (line.get("description") or "").strip()
            if not description:
                raise ValidationError(f"Line {index} is missing a description.")
            quantity = line.get("quantity") or Decimal("0")
            if quantity <= 0:
                raise ValidationError(f"Line {index} must have a quantity greater than zero.")
            unit_price = line.get("unit_price") or Decimal("0")
            if unit_price < 0:
                raise ValidationError(f"Line {index} cannot have a negative unit price.")
            discount_amount = line.get("discount_amount") or Decimal("0")
            line_total = (quantity * unit_price) - discount_amount
            prepared.append(
                {
                    "description": description,
                    "product_code": line.get("product_code", ""),
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "discount_amount": discount_amount,
                    "line_total": line_total,
                    "revenue_account": line.get("revenue_account"),
                    "tax_code": line.get("tax_code"),
                    "tax_amount": line.get("tax_amount") or Decimal("0"),
                }
            )
        if not prepared:
            raise ValidationError("At least one line item is required.")
        return prepared

    @transaction.atomic
    def create_order(
        self,
        *,
        organization,
        customer,
        currency,
        order_date,
        expected_ship_date=None,
        exchange_rate: Decimal = Decimal("1"),
        reference_number: str = "",
        notes: str = "",
        metadata: Optional[dict] = None,
        warehouse: Optional[Warehouse] = None,
        lines: Iterable[dict],
    ) -> SalesOrder:
        if customer.organization_id != organization.id:
            raise ValidationError("Customer must belong to the same organization.")

        prepared_lines = self._validate_line_payload(lines)
        metadata = metadata or {}

        order = SalesOrder.objects.create(
            organization=organization,
            customer=customer,
            customer_display_name=customer.display_name,
            currency=currency,
            order_date=order_date,
            expected_ship_date=expected_ship_date,
            exchange_rate=exchange_rate or Decimal("1"),
            reference_number=reference_number or "",
            notes=notes or "",
            metadata=metadata,
            warehouse=warehouse,
            created_by=self.user,
            updated_by=self.user,
        )

        for index, line in enumerate(prepared_lines, start=1):
            SalesOrderLine.objects.create(
                order=order,
                line_number=index,
                description=line["description"],
                product_code=line["product_code"],
                quantity=line["quantity"],
                unit_price=line["unit_price"],
                discount_amount=line["discount_amount"],
                line_total=line["line_total"],
                revenue_account=line["revenue_account"],
                tax_code=line["tax_code"],
                tax_amount=line["tax_amount"],
            )

        order.recompute_totals(save=True)
        return order

    @transaction.atomic
    def transition_status(self, order: SalesOrder, new_status: str) -> SalesOrder:
        current = order.status
        allowed = self.ALLOWED_TRANSITIONS.get(current, set())
        if new_status not in allowed:
            raise ValidationError(f"Cannot transition sales order from {current} to {new_status}.")
        order.status = new_status
        order.updated_by = self.user
        order.save(update_fields=["status", "updated_by", "updated_at"])
        return order

    def _get_product(self, order: SalesOrder, product_code: str) -> Optional[Product]:
        if not product_code:
            return None
        return Product.objects.filter(
            organization=order.organization, code=product_code
        ).select_related("organization").first()

    @transaction.atomic
    def reserve_stock(self, order: SalesOrder, warehouse: Optional[Warehouse] = None) -> dict:
        """Soft-allocate quantities to the order lines.

        Updates each line.allocated_quantity based on available stock at the given warehouse
        (or across all warehouses when none supplied). Returns a summary for UI.
        """
        warehouse = warehouse or order.warehouse
        summary = {"allocated": [], "shortages": []}
        for line in order.lines.select_related():
            product = self._get_product(order, line.product_code)
            if not product:
                summary["shortages"].append(
                    {"line": line.line_number, "product_code": line.product_code, "reason": "Product not found"}
                )
                line.allocated_quantity = Decimal("0")
                line.save(update_fields=["allocated_quantity", "updated_at"])
                continue
            qs = InventoryItem.objects.filter(organization=order.organization, product=product)
            if warehouse:
                qs = qs.filter(warehouse=warehouse)
            available = qs.aggregate(total=models.Sum("quantity_on_hand"))
            available_qty = available.get("total") or Decimal("0")
            allocate_qty = min(line.quantity, available_qty)
            line.allocated_quantity = allocate_qty
            line.save(update_fields=["allocated_quantity", "updated_at"])
            if allocate_qty < line.quantity:
                summary["shortages"].append(
                    {
                        "line": line.line_number,
                        "product_code": line.product_code,
                        "requested": line.quantity,
                        "allocated": allocate_qty,
                    }
                )
            else:
                summary["allocated"].append(
                    {
                        "line": line.line_number,
                        "product_code": line.product_code,
                        "allocated": allocate_qty,
                    }
                )
        order.updated_by = self.user
        order.save(update_fields=["updated_by", "updated_at"])
        return summary

    @transaction.atomic
    def confirm_order(self, order: SalesOrder, warehouse: Optional[Warehouse] = None) -> Tuple[SalesOrder, dict]:
        if order.status != "draft":
            raise ValidationError("Only draft orders can be confirmed.")
        if warehouse and warehouse.organization_id != order.organization_id:
            raise ValidationError("Warehouse must belong to the same organization.")

        if warehouse and order.warehouse_id != warehouse.id:
            order.warehouse = warehouse
            order.save(update_fields=["warehouse", "updated_at"])

        summary = self.reserve_stock(order, warehouse)
        order.status = "confirmed"
        order.updated_by = self.user
        order.save(update_fields=["status", "updated_by", "updated_at"])
        return order, summary

    @transaction.atomic
    def attach_invoice(self, order: SalesOrder, invoice: SalesInvoice) -> SalesOrder:
        if invoice.customer_id != order.customer_id:
            raise ValidationError("Invoice customer must match the sales order customer.")
        order.linked_invoice = invoice
        order.status = "invoiced"
        order.updated_by = self.user
        order.save(update_fields=["linked_invoice", "status", "updated_by", "updated_at"])
        return order

    @transaction.atomic
    def convert_to_invoice(
        self,
        order: SalesOrder,
        *,
        invoice_date,
        payment_term=None,
        due_date=None,
        journal_type=None,
        warehouse: Optional[Warehouse] = None,
        post_invoice: bool = False,
    ) -> SalesInvoice:
        if order.lines.count() == 0:
            raise ValidationError("Sales order must have lines before conversion.")
        warehouse = warehouse or order.warehouse
        service = SalesInvoiceService(self.user)
        line_payload = [
            {
                "description": line.description,
                "product_code": line.product_code,
                "quantity": line.quantity,
                "unit_price": line.unit_price,
                "discount_amount": line.discount_amount,
                "revenue_account": line.revenue_account,
                "tax_code": line.tax_code,
                "tax_amount": line.tax_amount,
                "metadata": {"source_order_line": line.pk},
            }
            for line in order.lines.order_by("line_number")
        ]
        invoice = service.create_invoice(
            organization=order.organization,
            customer=order.customer,
            invoice_number=None,
            invoice_date=invoice_date,
            currency=order.currency,
            lines=line_payload,
            payment_term=payment_term,
            due_date=due_date,
            exchange_rate=order.exchange_rate,
            metadata={"source_order": order.pk, **(order.metadata or {})},
        )
        self.attach_invoice(order, invoice)

        if post_invoice and journal_type:
            service.validate_invoice(invoice)
            service.post_invoice(invoice=invoice, journal_type=journal_type, warehouse=warehouse)
        return invoice
