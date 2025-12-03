from __future__ import annotations

from decimal import Decimal
from typing import Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounting.models import (
    AccountingPeriod,
    Journal,
    JournalLine,
    JournalType,
    LandedCostAllocation,
    LandedCostBasis,
    LandedCostDocument,
    PurchaseInvoice,
)
from accounting.services.posting_service import PostingService
from inventory.models import InventoryItem, Product, StockLedger


class LandedCostService:
    """Allocate and post landed cost against a posted purchase invoice."""

    def __init__(self, user):
        self.user = user
        self.posting_service = PostingService(user)

    def _get_period_for_date(self, organization, document_date):
        period = (
            AccountingPeriod.objects.filter(
                organization=organization,
                start_date__lte=document_date,
                end_date__gte=document_date,
                status="open",
            )
            .order_by("start_date")
            .first()
        )
        if not period:
            period = AccountingPeriod.get_current_period(organization)
        if not period:
            raise ValidationError("No open accounting period is available for the landed cost date.")
        return period

    def _resolve_journal_type(
        self, organization, invoice: PurchaseInvoice, journal_type: Optional[JournalType] = None
    ) -> JournalType:
        if journal_type:
            return journal_type
        if invoice.journal and invoice.journal.journal_type:
            return invoice.journal.journal_type
        preferred_codes = ("PI", "PUR", "PURCHASE", "GJ")
        for code in preferred_codes:
            jt = JournalType.objects.filter(organization=organization, code__iexact=code).first()
            if jt:
                return jt
        jt = (
            JournalType.objects.filter(organization=organization, name__icontains="purchase").first()
            or JournalType.objects.filter(organization=organization, is_system_type=True).first()
            or JournalType.objects.filter(organization=organization).first()
        )
        if not jt:
            raise ValidationError("No journal type configured for landed cost posting.")
        return jt

    @transaction.atomic
    def apply(self, document: LandedCostDocument, journal_type: Optional[JournalType] = None) -> Journal:
        if document.is_applied:
            return document.journal

        invoice = document.purchase_invoice
        organization = document.organization
        if invoice.organization_id != organization.id:
            raise ValidationError("Invoice and landed cost document must belong to the same organization.")
        if invoice.status != "posted":
            raise ValidationError("Landed cost can only be applied after the purchase invoice is posted.")
        if not invoice.warehouse:
            raise ValidationError("Warehouse is required on the purchase invoice to apply landed cost.")

        if document.currency_id is None:
            document.currency = invoice.currency
        exchange_rate = Decimal(document.exchange_rate or 0)
        if exchange_rate <= 0:
            exchange_rate = Decimal(invoice.exchange_rate or Decimal("1"))
            document.exchange_rate = exchange_rate
        if document.document_date is None:
            document.document_date = invoice.invoice_date
        document.save(update_fields=["currency", "exchange_rate", "document_date"])

        product_codes = [ln.product_code for ln in invoice.lines.all() if ln.product_code]
        products = Product.objects.filter(
            organization=organization, code__in=product_codes, is_inventory_item=True
        )
        product_map = {p.code: p for p in products}
        inventory_lines = [
            (line, product_map[line.product_code])
            for line in invoice.lines.all()
            if line.product_code in product_map
        ]
        if not inventory_lines:
            raise ValidationError("No inventory-bearing lines were found to allocate landed cost.")

        total_cost = sum((line.amount for line in document.cost_lines.all()), Decimal("0"))
        if total_cost <= 0:
            raise ValidationError("Total landed cost must be greater than zero.")

        if document.basis == LandedCostBasis.BY_QUANTITY:
            total_basis = sum((ln.quantity for ln, _ in inventory_lines), Decimal("0"))
            basis_getter = lambda ln: ln.quantity  # noqa: E731
        else:
            total_basis = sum((ln.line_total for ln, _ in inventory_lines), Decimal("0"))
            basis_getter = lambda ln: ln.line_total  # noqa: E731

        if total_basis <= 0:
            raise ValidationError("Allocation basis equals zero; cannot allocate landed cost.")

        LandedCostAllocation.objects.filter(document=document).delete()
        allocation_inputs = []
        remaining = total_cost
        for index, (line, product) in enumerate(inventory_lines, start=1):
            basis_value = basis_getter(line)
            factor = (basis_value / total_basis) if total_basis else Decimal("0")
            factor = factor.quantize(Decimal("0.00000001"))
            amount = (total_cost * factor).quantize(Decimal("0.0001"))
            if index == len(inventory_lines):
                amount = remaining
            else:
                remaining -= amount
            allocation_inputs.append((line, product, amount, factor))

        LandedCostAllocation.objects.bulk_create(
            [
                LandedCostAllocation(
                    document=document,
                    purchase_line=line,
                    amount=amount,
                    factor=factor,
                )
                for line, _, amount, factor in allocation_inputs
            ]
        )

        period = self._get_period_for_date(organization, document.document_date)
        resolved_journal_type = self._resolve_journal_type(organization, invoice, journal_type)
        journal = Journal.objects.create(
            organization=organization,
            journal_type=resolved_journal_type,
            period=period,
            journal_date=document.document_date,
            reference=f"LC-{invoice.invoice_number}",
            description=f"Landed cost for purchase invoice {invoice.invoice_number}",
            currency_code=document.currency.currency_code,
            exchange_rate=exchange_rate,
            status="draft",
            created_by=self.user,
            updated_by=self.user,
        )

        line_number = 1
        total_debit = Decimal("0")
        for line, product, amount, _ in allocation_inputs:
            inventory_account = getattr(product, "inventory_account", None)
            if not inventory_account:
                raise ValidationError(
                    f"Product {product.code} is missing an inventory account for landed cost allocation."
                )
            JournalLine.objects.create(
                journal=journal,
                line_number=line_number,
                account=inventory_account,
                description=f"Landed cost for {product.code}",
                debit_amount=amount,
                department=line.department,
                project=line.project,
                cost_center=line.cost_center,
                created_by=self.user,
            )
            total_debit += amount
            line_number += 1

            item, _ = InventoryItem.objects.get_or_create(
                organization=organization,
                product=product,
                warehouse=invoice.warehouse,
                defaults={"quantity_on_hand": Decimal("0"), "unit_cost": Decimal("0")},
            )
            if item.quantity_on_hand > 0:
                current_value = item.quantity_on_hand * item.unit_cost
                new_total_value = current_value + amount
                item.unit_cost = (new_total_value / item.quantity_on_hand).quantize(Decimal("0.0001"))
                item.save(update_fields=["unit_cost", "updated_at"])
            StockLedger.objects.create(
                organization=organization,
                product=product,
                warehouse=invoice.warehouse,
                txn_type="landed_cost",
                reference_id=f"LC-{invoice.invoice_number}",
                txn_date=document.document_date,
                qty_in=Decimal("0"),
                qty_out=Decimal("0"),
                unit_cost=item.unit_cost,
            )

        total_credit = Decimal("0")
        for cost_line in document.cost_lines.select_related("credit_account"):
            JournalLine.objects.create(
                journal=journal,
                line_number=line_number,
                account=cost_line.credit_account,
                description=f"Landed cost component: {cost_line.description}",
                credit_amount=cost_line.amount,
                created_by=self.user,
            )
            total_credit += cost_line.amount
            line_number += 1

        if total_debit.quantize(Decimal("0.01")) != total_credit.quantize(Decimal("0.01")):
            raise ValidationError(
                f"Landed cost journal is not balanced: debit={total_debit}, credit={total_credit}"
            )

        posted = self.posting_service.post(journal)
        document.journal = posted
        document.is_applied = True
        document.applied_at = timezone.now()
        document.save(update_fields=["journal", "is_applied", "applied_at", "updated_at"])
        return posted
