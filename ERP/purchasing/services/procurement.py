from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils.timezone import now
from django.conf import settings
from django.utils import timezone

from inventory.models import InventoryItem, StockLedger
from accounting.models import (
    AccountingPeriod,
    Journal,
    JournalLine,
    JournalType,
)
from accounting.services.posting_service import PostingService
from accounting.services.post_journal import post_journal

from purchasing.models import (
    LandedCostAllocation,
    LandedCostBasis,
    LandedCostDocument,
    PurchaseInvoice,
)


class ProcurementPostingError(Exception):
    """Domain-specific error raised when procurement posting fails."""


def _get_period_for_date(organization, document_date):
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
        raise ProcurementPostingError("No open accounting period is available for posting.")
    return period


def _get_purchase_journal_type(organization):
    preferred_codes = ("PJ", "PUR", "PURCHASE", "GJ")
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
        raise ProcurementPostingError("No journal type configured for purchasing entries.")
    return jt


def _resolve_journal_date(invoice_date):
    """
    Decide journal date based on configuration.
    Default: invoice date. Optional override: posting date (today) via PURCHASE_JOURNAL_DATE_MODE.
    """
    mode = str(getattr(settings, "PURCHASE_JOURNAL_DATE_MODE", "invoice_date")).lower()
    if mode == "posting_date":
        return timezone.localdate()
    return invoice_date


@transaction.atomic
def post_purchase_invoice(pi: PurchaseInvoice) -> PurchaseInvoice:
    """Post a purchase invoice into inventory and the general ledger."""

    if pi.status == 'posted':
        return pi

    if not pi.lines.exists():
        raise ProcurementPostingError("Purchase invoice must have at least one line before posting.")

    pi.recompute_totals(save=False)
    pi.save(
        update_fields=["subtotal", "tax_total", "total", "base_currency_total", "updated_at"],
    )

    organization = pi.organization
    period = _get_period_for_date(organization, pi.invoice_date)
    journal_type = _get_purchase_journal_type(organization)

    journal = Journal.objects.create(
        organization=organization,
        journal_type=journal_type,
        period=period,
        journal_date=_resolve_journal_date(pi.invoice_date),
        reference=f"PI-{pi.number}",
        description=f"Purchase invoice {pi.number} - {pi.vendor_display_name}",
        currency_code=pi.currency.currency_code,
        exchange_rate=pi.exchange_rate,
        status="draft",
    )

    line_number = 1
    total_debit = Decimal("0")
    total_credit = Decimal("0")

    lines = list(
        pi.lines.select_related(
            "product",
            "product__inventory_account",
            "product__expense_account",
            "warehouse",
            "input_vat_account",
        )
    )
    subtotal_before_discount = sum((ln.line_subtotal for ln in lines), Decimal("0"))
    header_discount = pi.discount_amount or Decimal("0")
    remaining_discount = header_discount
    if header_discount < 0:
        raise ProcurementPostingError("Header discount cannot be negative during posting.")
    if header_discount > subtotal_before_discount:
        raise ProcurementPostingError("Header discount exceeds line subtotal; cannot post journal.")

    for idx, line in enumerate(lines):
        discount_share = Decimal("0")
        if header_discount and subtotal_before_discount > 0:
            if idx == (len(lines) - 1):
                discount_share = remaining_discount
            else:
                factor = (line.line_subtotal / subtotal_before_discount)
                discount_share = (header_discount * factor).quantize(Decimal("0.01"))
                remaining_discount -= discount_share
        line_value = (line.line_subtotal - discount_share).quantize(Decimal("0.01"))
        if line_value <= 0:
            line_value = Decimal("0")
        if line_value == 0:
            continue
        line_tax = line.line_tax_amount
        if line_tax <= 0:
            line_tax = Decimal("0")

        if line.product.is_inventory_item:
            inventory_account = getattr(line.product, "inventory_account", None)
            if not inventory_account:
                raise ProcurementPostingError(
                    f"Product {line.product} is missing an inventory account."
                )
            JournalLine.objects.create(
                journal=journal,
                line_number=line_number,
                account=inventory_account,
                description=f"Inventory: {line.product}",
                debit_amount=line_value,
            )
            line_number += 1
            total_debit += line_value
        else:
            expense_account = line.account or getattr(line.product, "expense_account", None)
            if not expense_account:
                raise ProcurementPostingError(
                    f"Purchase line for {line.product} is missing an expense account."
                )
            JournalLine.objects.create(
                journal=journal,
                line_number=line_number,
                account=expense_account,
                description=line.description or f"Expense: {line.product}",
                debit_amount=line_value,
            )
            line_number += 1
            total_debit += line_value

        if line_tax and line_tax != Decimal("0"):
            tax_account = line.input_vat_account or getattr(line.tax_code, "purchase_account", None)
            if not tax_account:
                raise ProcurementPostingError(
                    f"VAT account missing for line {getattr(line, 'pk', None) or line.line_number} with tax amount {line_tax}."
                )
            JournalLine.objects.create(
                journal=journal,
                line_number=line_number,
                account=tax_account,
                description=f"Input VAT: {line.product}",
                debit_amount=line_tax,
            )
            line_number += 1
            total_debit += line_tax

    ap_account = getattr(pi.vendor, "accounts_payable_account", None)
    if not ap_account:
        raise ProcurementPostingError(f"Supplier {pi.vendor_display_name} has no Accounts Payable account.")

    rounding = getattr(pi, "rounding_adjustment", None) or Decimal("0")
    if rounding:
        rounding_account = pi.purchase_account or ap_account
        if not rounding_account:
            raise ProcurementPostingError("No account available to book rounding adjustment for purchase invoice.")
        debit_amt = rounding if rounding > 0 else Decimal("0")
        credit_amt = abs(rounding) if rounding < 0 else Decimal("0")
        JournalLine.objects.create(
            journal=journal,
            line_number=line_number,
            account=rounding_account,
            description="Rounding adjustment",
            debit_amount=debit_amt,
            credit_amount=credit_amt,
        )
        total_debit += debit_amt
        total_credit += credit_amt
        line_number += 1

    ap_amount = (pi.total or Decimal("0")).quantize(Decimal("0.01"))
    if ap_amount <= 0:
        raise ProcurementPostingError("Invoice total must be greater than zero to post journal.")

    JournalLine.objects.create(
        journal=journal,
        line_number=line_number,
        account=ap_account,
        description=f"Accounts Payable - {pi.vendor_display_name}",
        credit_amount=ap_amount,
    )
    total_credit += ap_amount

    if total_debit.quantize(Decimal("0.01")) != total_credit.quantize(Decimal("0.01")):
        raise ProcurementPostingError(
            f"Journal is not balanced: debit={total_debit}, credit={total_credit}"
        )

    for line in lines:
        if not line.product.is_inventory_item:
            continue
        unit_cost = line.unit_price
        StockLedger.objects.create(
            organization=organization,
            product=line.product,
            warehouse=line.warehouse,
            txn_type="purchase",
            reference_id=f"PI-{pi.number}",
            txn_date=pi.invoice_date,
            qty_in=line.quantity,
            qty_out=Decimal("0"),
            unit_cost=unit_cost,
        )
        item, _ = InventoryItem.objects.get_or_create(
            organization=organization,
            product=line.product,
            warehouse=line.warehouse,
            defaults={"quantity_on_hand": Decimal("0"), "unit_cost": Decimal("0")},
        )
        old_qty = item.quantity_on_hand
        old_cost = item.unit_cost
        new_qty = old_qty + line.quantity
        if new_qty <= 0:
            raise ProcurementPostingError(
                f"Weighted cost calculation invalid for {line.product}; quantity would be <= 0."
            )
        new_total_value = (old_qty * old_cost) + (line.quantity * unit_cost)
        item.quantity_on_hand = new_qty
        item.unit_cost = (new_total_value / new_qty).quantize(Decimal("0.0001"))
        item.save(update_fields=["quantity_on_hand", "unit_cost", "updated_at"])

    post_journal(journal)

    pi.status = 'posted'
    pi.journal = journal
    PurchaseInvoice.objects.filter(pk=pi.pk).update(status=pi.status, journal=journal)

    # Record vendor price history
    from inventory.services.price_history_service import PriceHistoryService
    price_service = PriceHistoryService()
    for line in pi.lines.select_related('product'):
        price_service.record_vendor_price_history(
            vendor=pi.vendor,
            product=line.product,
            unit_price=line.unit_price,
            doc_date=pi.invoice_date,
            organization=pi.organization,
            created_by=pi.created_by,
            currency=getattr(pi.currency, "currency_code", None),
            quantity=line.quantity,
            doc_ref=f"PI-{pi.number}",
        )

    return pi


@transaction.atomic
def reverse_purchase_invoice(pi: PurchaseInvoice, *, user=None) -> PurchaseInvoice:
    """Reverse a posted purchase invoice by creating reversing GL and stock movements.

    - Creates a reversing journal via PostingService
    - Pushes negative stock movements for inventory lines and updates InventoryItem
    - Marks the invoice back to draft and detaches the posted journal
    """
    if pi.status != 'posted':
        raise ProcurementPostingError("Only posted purchase invoices can be reversed.")
    if not pi.journal:
        raise ProcurementPostingError("Posted purchase invoice is missing its journal; cannot reverse.")

    # Reverse GL first
    if not user:
        raise ProcurementPostingError("User is required to reverse a purchase invoice.")
    PostingService(user).reverse(pi.journal)

    # Reverse inventory movements
    for line in pi.lines.select_related("product", "warehouse"):
        if not line.product.is_inventory_item:
            continue

        try:
            item = InventoryItem.objects.select_for_update().get(
                organization=pi.organization,
                product=line.product,
                warehouse=line.warehouse,
            )
        except InventoryItem.DoesNotExist as exc:
            raise ProcurementPostingError(
                f"Inventory snapshot missing for {line.product} @ {line.warehouse}; cannot reverse."
            ) from exc

        old_qty = item.quantity_on_hand
        if old_qty < line.quantity:
            raise ProcurementPostingError(
                f"Cannot reverse {line.product}: on hand {old_qty} < reversal qty {line.quantity}."
            )

        reverse_qty = line.quantity
        reversal_reference = f"REV-PI-{pi.number}"
        StockLedger.objects.create(
            organization=pi.organization,
            product=line.product,
            warehouse=line.warehouse,
            txn_type="purchase_return",
            reference_id=reversal_reference,
            txn_date=pi.invoice_date,
            qty_in=Decimal("0"),
            qty_out=reverse_qty,
            unit_cost=line.unit_price,
        )

        new_total_value = (old_qty * item.unit_cost) - (reverse_qty * line.unit_price)
        new_qty = old_qty - reverse_qty
        item.quantity_on_hand = new_qty
        item.unit_cost = (
            (new_total_value / new_qty).quantize(Decimal("0.0001")) if new_qty > 0 else Decimal("0")
        )
        item.save(update_fields=["quantity_on_hand", "unit_cost", "updated_at"])

    # Move invoice back to draft and detach journal
    PurchaseInvoice.objects.filter(pk=pi.pk).update(
        status='draft',
        journal=None,
    )
    pi.refresh_from_db()
    return pi


@transaction.atomic
def apply_landed_cost_document(doc: LandedCostDocument) -> LandedCostDocument:
    """Allocate landed cost to inventory lines, update stock, and post GL adjustment."""

    if doc.is_applied:
        return doc

    pi = doc.purchase_invoice
    if pi.status != 'posted':
        raise ProcurementPostingError("Landed cost can only be applied once the invoice is posted.")
    if doc.organization_id != pi.organization_id:
        raise ProcurementPostingError("Landed cost document and invoice organization mismatch.")

    inv_lines = list(
        pi.lines.select_related("product", "warehouse", "product__inventory_account")
        .filter(product__is_inventory_item=True)
        .order_by("id")
    )
    if not inv_lines:
        raise ProcurementPostingError("No inventory lines available for landed cost allocation.")

    total_cost = sum((line.amount for line in doc.cost_lines.all()), Decimal("0"))
    if total_cost <= 0:
        raise ProcurementPostingError("Total landed cost must be greater than zero.")

    if doc.basis == LandedCostBasis.BY_VALUE:
        total_basis = sum((ln.line_subtotal for ln in inv_lines), Decimal("0"))
        basis_getter = lambda ln: ln.line_subtotal  # noqa: E731 - simple inline helper
    else:
        total_basis = sum((ln.quantity for ln in inv_lines), Decimal("0"))
        basis_getter = lambda ln: ln.quantity  # noqa: E731 - simple inline helper

    if total_basis <= 0:
        raise ProcurementPostingError("Allocation basis equals zero; cannot allocate landed cost.")

    LandedCostAllocation.objects.filter(document=doc).delete()
    allocations = []
    remaining = total_cost
    for index, line in enumerate(inv_lines, start=1):
        basis_value = basis_getter(line)
        factor = (basis_value / total_basis) if total_basis else Decimal("0")
        factor = factor.quantize(Decimal("0.00000001"))
        amount = (total_cost * factor).quantize(Decimal("0.0001"))
        if index == len(inv_lines):
            amount = remaining
        else:
            remaining -= amount
        allocations.append(
            LandedCostAllocation(
                document=doc,
                purchase_line=line,
                amount=amount,
                factor=factor,
            )
        )
    LandedCostAllocation.objects.bulk_create(allocations)

    organization = doc.organization
    period = _get_period_for_date(organization, doc.document_date)
    journal_type = _get_purchase_journal_type(organization)
    journal = Journal.objects.create(
        organization=organization,
        journal_type=journal_type,
        period=period,
        journal_date=doc.document_date,
        reference=f"LC-{pi.number}",
        description=f"Landed cost for purchase invoice {pi.number}",
        currency_code=pi.currency.currency_code,
        exchange_rate=pi.exchange_rate,
        status="draft",
    )

    total_debit = Decimal("0")
    total_credit = Decimal("0")
    line_number = 1

    for alloc in doc.allocations.select_related("purchase_line__product", "purchase_line__warehouse"):
        purchase_line = alloc.purchase_line
        product = purchase_line.product
        inventory_account = getattr(product, "inventory_account", None)
        if not inventory_account:
            raise ProcurementPostingError(f"Product {product} has no inventory account configured.")
        JournalLine.objects.create(
            journal=journal,
            line_number=line_number,
            account=inventory_account,
            description=f"Landed cost: {product}",
            debit_amount=alloc.amount,
        )
        line_number += 1
        total_debit += alloc.amount

        try:
            item = InventoryItem.objects.get(
                organization=organization,
                product=product,
                warehouse=purchase_line.warehouse,
            )
        except InventoryItem.DoesNotExist as exc:  # pragma: no cover - defensive safety
            raise ProcurementPostingError(
                f"Inventory snapshot missing for {product} @ {purchase_line.warehouse}."
            ) from exc

        if item.quantity_on_hand > 0:
            current_value = item.quantity_on_hand * item.unit_cost
            new_total_value = current_value + alloc.amount
            item.unit_cost = (new_total_value / item.quantity_on_hand).quantize(Decimal("0.0001"))
            item.save(update_fields=["unit_cost", "updated_at"])

        StockLedger.objects.create(
            organization=organization,
            product=product,
            warehouse=purchase_line.warehouse,
            txn_type="landed_cost",
            reference_id=f"LC-{pi.number}",
            txn_date=doc.document_date,
            qty_in=Decimal("0"),
            qty_out=Decimal("0"),
            unit_cost=item.unit_cost,
        )

    for cost_line in doc.cost_lines.select_related("gl_account"):
        JournalLine.objects.create(
            journal=journal,
            line_number=line_number,
            account=cost_line.gl_account,
            description=f"Landed cost component: {cost_line.description}",
            credit_amount=cost_line.amount,
        )
        line_number += 1
        total_credit += cost_line.amount

    if total_debit.quantize(Decimal("0.01")) != total_credit.quantize(Decimal("0.01")):
        raise ProcurementPostingError(
            f"Landed cost journal is not balanced: debit={total_debit}, credit={total_credit}"
        )

    post_journal(journal)

    doc.is_applied = True
    doc.applied_at = now()
    doc.save(update_fields=["is_applied", "applied_at"])

    return doc
