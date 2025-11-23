from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Optional

from django.core.exceptions import ValidationError
from django.db import transaction

from accounting.models import SalesInvoice, SalesOrder, SalesOrderLine
from accounting.services.sales_invoice_service import SalesInvoiceService


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
            prepared.append(
                {
                    "description": description,
                    "product_code": line.get("product_code", ""),
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "discount_amount": line.get("discount_amount") or Decimal("0"),
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
    ) -> SalesInvoice:
        if order.lines.count() == 0:
            raise ValidationError("Sales order must have lines before conversion.")
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
        return invoice
