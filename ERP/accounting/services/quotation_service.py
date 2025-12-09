from __future__ import annotations

from decimal import Decimal
import logging

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounting.models import (
    Quotation,
    SalesOrder,
    SalesOrderLine,
)
from accounting.services.sales_invoice_service import SalesInvoiceService
from accounting.utils.event_utils import emit_integration_event


logger = logging.getLogger(__name__)


class QuotationService:
    """Encapsulates business rules around quotations."""

    def __init__(self, user):
        self.user = user
        self.invoice_service = SalesInvoiceService(user)

    def _build_line_payload(self, quotation: Quotation) -> list[dict]:
        payload = []
        for line in quotation.lines.order_by('line_number'):
            payload.append(
                {
                    'description': line.description,
                    'product_code': line.product_code,
                    'quantity': line.quantity,
                    'unit_price': line.unit_price,
                    'discount_amount': line.discount_amount,
                    'revenue_account': line.revenue_account,
                    'tax_code': line.tax_code,
                    'tax_amount': line.tax_amount,
                    'cost_center': line.cost_center,
                    'department': line.department,
                    'project': line.project,
                    'dimension_value': line.dimension_value,
                    'metadata': line.metadata,
                }
            )
        return payload

    def _throw_if_not_convertible(self, quotation: Quotation):
        if not quotation.can_be_converted:
            raise ValidationError("Quotation cannot be converted in its current state.")

    @transaction.atomic
    def convert_to_invoice(
        self,
        quotation: Quotation,
        invoice_date=None,
    ):
        self._throw_if_not_convertible(quotation)
        line_payload = self._build_line_payload(quotation)
        if not line_payload:
            raise ValidationError("Quotation must have at least one line to convert.")

        invoice = self.invoice_service.create_invoice(
            organization=quotation.organization,
            customer=quotation.customer,
            invoice_date=invoice_date or quotation.quotation_date or timezone.now().date(),
            currency=quotation.currency,
            lines=line_payload,
            payment_term=quotation.payment_term,
            due_date=quotation.due_date,
            exchange_rate=quotation.exchange_rate,
            metadata=quotation.metadata or {},
        )
        if quotation.reference_number and not invoice.reference_number:
            invoice.reference_number = quotation.reference_number
        if not invoice.notes and quotation.notes:
            invoice.notes = quotation.notes
        invoice.save(update_fields=['reference_number', 'notes'])

        quotation.linked_sales_invoice = invoice
        quotation.status = Quotation.STATUS_CONVERTED
        quotation.converted_at = timezone.now()
        quotation.save(update_fields=['status', 'converted_at', 'linked_sales_invoice', 'updated_at'])

        emit_integration_event(
            'quotation_converted_to_invoice',
            quotation,
            {
                'quotation_number': quotation.quotation_number,
                'invoice_number': invoice.invoice_number,
                'total': str(invoice.total),
            },
        )
        return invoice

    @transaction.atomic
    def convert_to_sales_order(self, quotation: Quotation, expected_ship_date=None):
        self._throw_if_not_convertible(quotation)
        line_payload = self._build_line_payload(quotation)
        if not line_payload:
            raise ValidationError("Quotation must have at least one line to convert.")

        order = SalesOrder.objects.create(
            organization=quotation.organization,
            customer=quotation.customer,
            customer_display_name=quotation.customer_display_name,
            order_date=quotation.quotation_date,
            expected_ship_date=expected_ship_date or quotation.valid_until,
            currency=quotation.currency,
            exchange_rate=quotation.exchange_rate,
            reference_number=quotation.reference_number,
            notes=quotation.notes,
            metadata=quotation.metadata or {},
            created_by=self.user,
            updated_by=self.user,
        )

        for index, line_data in enumerate(line_payload, start=1):
            SalesOrderLine.objects.create(
                order=order,
                line_number=index,
                description=line_data.get('description', ''),
                product_code=line_data.get('product_code', ''),
                quantity=line_data.get('quantity', Decimal('1')),
                unit_price=line_data.get('unit_price', Decimal('0')),
                discount_amount=line_data.get('discount_amount', Decimal('0')),
                revenue_account=line_data.get('revenue_account'),
                tax_code=line_data.get('tax_code'),
                tax_amount=line_data.get('tax_amount', Decimal('0')),
                metadata=line_data.get('metadata', {}),
            )
        order.recompute_totals(save=True)

        quotation.linked_sales_order = order
        quotation.status = Quotation.STATUS_CONVERTED
        quotation.converted_at = timezone.now()
        quotation.save(update_fields=['status', 'converted_at', 'linked_sales_order', 'updated_at'])

        emit_integration_event(
            'quotation_converted_to_order',
            quotation,
            {
                'quotation_number': quotation.quotation_number,
                'order_number': order.order_number,
                'total': str(order.total),
            },
        )
        return order

    def mark_sent(self, quotation: Quotation):
        if quotation.status != Quotation.STATUS_DRAFT:
            raise ValidationError("Only drafts can be marked as sent.")
        quotation.status = Quotation.STATUS_SENT
        quotation.sent_at = timezone.now()
        quotation.save(update_fields=['status', 'sent_at', 'updated_at'])
        return quotation

    def mark_accepted(self, quotation: Quotation):
        if quotation.status not in {Quotation.STATUS_SENT, Quotation.STATUS_DRAFT}:
            raise ValidationError("Only sent quotations can be accepted.")
        quotation.status = Quotation.STATUS_ACCEPTED
        quotation.accepted_at = timezone.now()
        quotation.save(update_fields=['status', 'accepted_at', 'updated_at'])
        return quotation

    def mark_expired(self, quotation: Quotation):
        quotation.status = Quotation.STATUS_EXPIRED
        quotation.expired_at = timezone.now()
        quotation.save(update_fields=['status', 'expired_at', 'updated_at'])
        return quotation
