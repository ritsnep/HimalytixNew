from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, Iterable, Tuple

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from accounting.models import (
    AccountingPeriod,
    ChartOfAccount,
    Journal,
    JournalLine,
    JournalType,
)
from accounting.services.posting_service import PostingService
from lpg_vertical.models import (
    ConversionRule,
    CylinderSKU,
    InventoryMovement,
    LogisticsTrip,
    NocPurchase,
    SalesInvoice,
    SalesInvoiceLine,
)
from usermanagement.models import CompanyConfig, Organization


def get_company_config(company: Organization) -> CompanyConfig:
    defaults = CompanyConfig.defaults_for_vertical(getattr(company, "vertical_type", "retailer"))
    config, _ = CompanyConfig.objects.get_or_create(company=company, defaults=defaults)
    return config


def _pick_account(
    organization: Organization,
    nature: str,
    name_hint: str | None = None,
    require_bank: bool | None = None,
) -> ChartOfAccount | None:
    qs = ChartOfAccount.objects.filter(organization=organization, account_type__nature=nature)
    if require_bank is True:
        qs = qs.filter(is_bank_account=True)
    if name_hint:
        account = qs.filter(account_name__icontains=name_hint).first()
        if account:
            return account
    return qs.first()


def _get_open_period(org: Organization, target_date: date):
    period = AccountingPeriod.objects.filter(
        organization=org,
        start_date__lte=target_date,
        end_date__gte=target_date,
        status="open",
    ).first()
    if period:
        return period
    return AccountingPeriod.objects.filter(organization=org, is_current=True).first()


def _get_journal_type(org: Organization, code: str, name: str) -> JournalType:
    jt = JournalType.objects.filter(organization=org, code__iexact=code).first()
    if jt:
        return jt
    jt = JournalType.objects.filter(organization=org).first()
    if jt:
        return jt
    return JournalType.objects.create(
        organization=org,
        code=code,
        name=name,
        description=f"Auto-created for {name}",
        sequence_next=1,
        sequence_padding=3,
    )


def _create_journal(
    org: Organization,
    journal_date: date,
    description: str,
    lines: Iterable[Dict],
    journal_type_code: str,
    user=None,
) -> Journal:
    period = _get_open_period(org, journal_date)
    if period is None:
        raise ValidationError("No open accounting period found for posting date.")

    journal_type = _get_journal_type(org, journal_type_code, "LPG Auto")
    journal_number = journal_type.get_next_journal_number(period=period)

    journal = Journal.objects.create(
        organization=org,
        journal_number=journal_number,
        journal_type=journal_type,
        period=period,
        journal_date=journal_date,
        description=description,
        currency_code=getattr(org, "base_currency_code", "USD"),
        status="draft",
        created_by=user,
    )

    total_debit = Decimal("0")
    total_credit = Decimal("0")
    for idx, line in enumerate(lines, start=1):
        debit = Decimal(line.get("debit", 0) or 0)
        credit = Decimal(line.get("credit", 0) or 0)
        total_debit += debit
        total_credit += credit
        JournalLine.objects.create(
            journal=journal,
            line_number=idx,
            account=line["account"],
            description=line.get("description") or description,
            debit_amount=debit,
            credit_amount=credit,
            created_by=user,
        )

    if total_debit != total_credit:
        journal.lines.all().delete()
        journal.delete()
        raise ValidationError("Journal is not balanced.")

    journal.update_totals()
    posting = PostingService(user)
    posting.validate(journal)
    posting.post(journal)
    return journal


def allocate_lpg_to_cylinders(noc_purchase: NocPurchase) -> Dict[CylinderSKU, int]:
    """
    Convert MT into cylinder counts using ConversionRule (default rules per cylinder type).
    """
    rules = (
        ConversionRule.objects.filter(
            organization=noc_purchase.organization,
            is_default=True,
        )
        .select_related("cylinder_type")
        .order_by("cylinder_type__kg_per_cylinder")
    )
    if not rules.exists():
        return {}

    allocations: Dict[CylinderSKU, int] = {}
    remaining_mt = Decimal(noc_purchase.quantity_mt or 0)

    for rule in rules:
        if rule.mt_fraction_per_cylinder <= 0:
            continue
        possible_count = int(remaining_mt / rule.mt_fraction_per_cylinder)
        if possible_count <= 0:
            continue
        filled_sku = (
            CylinderSKU.objects.filter(
                organization=noc_purchase.organization,
                cylinder_type=rule.cylinder_type,
                state=CylinderSKU.STATE_FILLED,
            ).first()
        )
        if filled_sku:
            allocations[filled_sku] = possible_count
            remaining_mt -= rule.mt_fraction_per_cylinder * possible_count

    return allocations


@transaction.atomic
def post_noc_purchase(noc_purchase: NocPurchase, user=None) -> NocPurchase:
    if noc_purchase.status == NocPurchase.STATUS_POSTED:
        return noc_purchase

    org = noc_purchase.organization
    config = get_company_config(org)
    if not config.enable_noc_purchases:
        raise ValidationError("NOC purchases are disabled for this company.")

    inv_account = _pick_account(org, "asset", "inventory") or _pick_account(org, "asset", None)
    freight_account = _pick_account(org, "expense", "freight") or _pick_account(org, "expense", None)
    tax_account = _pick_account(org, "liability", "vat") or _pick_account(org, "asset", "tax")
    ap_account = _pick_account(org, "liability", "payable") or _pick_account(org, "liability", None)

    if not inv_account or not ap_account:
        raise ValidationError("Missing inventory or accounts payable account for posting.")

    lines = [
        {"account": inv_account, "debit": noc_purchase.subtotal, "description": "LPG Inventory"},
    ]
    if (noc_purchase.transport_cost or 0) > 0 and freight_account:
        lines.append({"account": freight_account, "debit": noc_purchase.transport_cost, "description": "Freight In"})
    if (noc_purchase.tax_amount or 0) > 0 and tax_account:
        lines.append({"account": tax_account, "debit": noc_purchase.tax_amount, "description": "Input VAT"})

    lines.append(
        {"account": ap_account, "credit": noc_purchase.total_amount, "description": "NOC Accounts Payable"}
    )

    journal = _create_journal(
        org=org,
        journal_date=noc_purchase.date,
        description=f"NOC Purchase {noc_purchase.bill_no}",
        lines=lines,
        journal_type_code="PUR",
        user=user or noc_purchase.created_by,
    )

    allocations = allocate_lpg_to_cylinders(noc_purchase)
    allocation_snapshot = {}
    for sku, qty in allocations.items():
        InventoryMovement.objects.create(
            organization=org,
            date=noc_purchase.date,
            cylinder_sku=sku,
            quantity=Decimal(qty),
            movement_type="purchase_noc",
            dest_location=noc_purchase.receipt_location,
            ref_doc_type="noc_purchase",
            ref_doc_id=noc_purchase.id,
            created_by=user,
        )
        allocation_snapshot[sku.code] = qty

    noc_purchase.posted_journal = journal
    noc_purchase.allocation_snapshot = allocation_snapshot
    noc_purchase.status = NocPurchase.STATUS_POSTED
    noc_purchase.save(update_fields=["posted_journal", "allocation_snapshot", "status", "updated_at"])
    return noc_purchase


def _find_empty_sku(org: Organization, cylinder_type) -> CylinderSKU | None:
    if cylinder_type is None:
        return CylinderSKU.objects.filter(organization=org, state=CylinderSKU.STATE_EMPTY).first()
    return (
        CylinderSKU.objects.filter(
            organization=org,
            cylinder_type=cylinder_type,
            state=CylinderSKU.STATE_EMPTY,
        ).first()
    )


def _enforce_credit(invoice: SalesInvoice, config: CompanyConfig):
    dealer = invoice.dealer
    if not dealer or dealer.credit_limit is None:
        return

    outstanding = (
        SalesInvoice.objects.filter(
            organization=invoice.organization,
            dealer=dealer,
            status="posted",
            payment_type="credit",
        )
        .exclude(pk=invoice.pk)
        .aggregate(total=Sum("total_amount"))
        .get("total")
        or Decimal("0")
    )

    projected = outstanding + (invoice.total_amount or Decimal("0"))
    if dealer.credit_limit and projected > dealer.credit_limit:
        if config.credit_enforcement_mode == "block":
            raise ValidationError(
                f"Dealer credit limit exceeded. Outstanding {outstanding} + invoice {invoice.total_amount} "
                f"> limit {dealer.credit_limit}."
            )
        # warn-only mode
        invoice.notes = (invoice.notes or "") + " Credit limit exceeded; proceed with caution."


@transaction.atomic
def post_sales_invoice(invoice: SalesInvoice, user=None) -> SalesInvoice:
    if invoice.status == "posted":
        return invoice

    org = invoice.organization
    config = get_company_config(org)
    if not config.enable_dealer_management and invoice.dealer_id:
        raise ValidationError("Dealer management disabled for this company.")

    for line in invoice.lines.all():
        line.compute_totals()
        line.save(update_fields=["tax_amount", "line_total"])

    invoice.recompute_totals()
    _enforce_credit(invoice, config)

    revenue_account = _pick_account(org, "income", "sales") or _pick_account(org, "income", None)
    ar_account = _pick_account(org, "asset", "receivable")
    cash_account = _pick_account(org, "asset", None, require_bank=True) or _pick_account(org, "asset", None)
    vat_output_account = _pick_account(org, "liability", "vat") or _pick_account(org, "liability", None)

    if invoice.payment_type == "credit" and not ar_account:
        raise ValidationError("Accounts receivable account not configured.")
    if invoice.payment_type != "credit" and not cash_account:
        raise ValidationError("Cash/Bank account not configured.")
    if not revenue_account:
        raise ValidationError("Revenue account not configured.")

    counter_account = ar_account if invoice.payment_type == "credit" else cash_account
    lines = [
        {"account": counter_account, "debit": invoice.total_amount, "description": f"Invoice {invoice.invoice_no}"},
        {"account": revenue_account, "credit": invoice.taxable_amount, "description": "Sales Revenue"},
    ]
    if (invoice.tax_amount or 0) > 0 and vat_output_account:
        lines.append({"account": vat_output_account, "credit": invoice.tax_amount, "description": "VAT Output"})

    journal = _create_journal(
        org=org,
        journal_date=invoice.date,
        description=f"Sales Invoice {invoice.invoice_no}",
        lines=lines,
        journal_type_code="SAL",
        user=user,
    )

    # Inventory movements
    for line in invoice.lines.select_related("cylinder_sku"):
        if line.cylinder_sku and line.cylinder_sku.state == CylinderSKU.STATE_FILLED:
            InventoryMovement.objects.create(
                organization=org,
                date=invoice.date,
                cylinder_sku=line.cylinder_sku,
                quantity=line.quantity,
                movement_type="sale",
                ref_doc_type="sales_invoice",
                ref_doc_id=invoice.id,
                created_by=user,
            )
    if invoice.empty_cylinders_collected > 0:
        base_line = invoice.lines.filter(cylinder_sku__isnull=False).first()
        empty_sku = _find_empty_sku(org, base_line.cylinder_sku.cylinder_type if base_line else None)
        if empty_sku:
            InventoryMovement.objects.create(
                organization=org,
                date=invoice.date,
                cylinder_sku=empty_sku,
                quantity=Decimal(invoice.empty_cylinders_collected),
                movement_type="empty_collection",
                ref_doc_type="sales_invoice",
                ref_doc_id=invoice.id,
                created_by=user,
            )

    invoice.posted_journal = journal
    invoice.status = "posted"
    invoice.save(
        update_fields=[
            "status",
            "posted_journal",
            "taxable_amount",
            "tax_amount",
            "total_amount",
            "notes",
            "updated_at",
        ]
    )
    return invoice


@transaction.atomic
def post_logistics_trip(trip: LogisticsTrip, user=None) -> LogisticsTrip:
    if trip.status == "posted":
        return trip

    org = trip.organization
    config = get_company_config(org)
    if not config.enable_logistics:
        raise ValidationError("Logistics module disabled for this company.")

    # Inventory transfer
    InventoryMovement.objects.create(
        organization=org,
        date=trip.date,
        cylinder_sku=trip.cylinder_sku,
        quantity=Decimal(trip.cylinder_count),
        movement_type="transfer_out",
        source_location=trip.from_location,
        dest_location=trip.to_location,
        ref_doc_type="logistics_trip",
        ref_doc_id=trip.id,
        created_by=user,
    )
    InventoryMovement.objects.create(
        organization=org,
        date=trip.date,
        cylinder_sku=trip.cylinder_sku,
        quantity=Decimal(trip.cylinder_count),
        movement_type="transfer_in",
        source_location=trip.from_location,
        dest_location=trip.to_location,
        ref_doc_type="logistics_trip",
        ref_doc_id=trip.id,
        created_by=user,
    )

    expense_account = _pick_account(org, "expense", "logistics") or _pick_account(org, "expense", None)
    cash_account = _pick_account(org, "asset", None, require_bank=True) or _pick_account(org, "liability", "payable")
    journal = None
    if trip.cost and expense_account and cash_account:
        journal = _create_journal(
            org=org,
            journal_date=trip.date,
            description=f"Logistics Trip {trip.id}",
            lines=[
                {"account": expense_account, "debit": trip.cost, "description": "Logistics Expense"},
                {"account": cash_account, "credit": trip.cost, "description": "Cash/Payable"},
            ],
            journal_type_code="LOG",
            user=user,
        )

    trip.posted_journal = journal
    trip.status = "posted"
    trip.save(update_fields=["status", "posted_journal", "updated_at"])
    return trip


def get_stock_balance(org: Organization, sku: CylinderSKU, location: str | None = None) -> Decimal:
    qs = InventoryMovement.objects.filter(organization=org, cylinder_sku=sku)
    if location:
        qs = qs.filter(dest_location=location) | qs.filter(source_location=location)
    total = sum((mv.signed_quantity for mv in qs), Decimal("0"))
    return total


def dashboard_summary(org: Organization, start_date: date, end_date: date) -> Dict:
    invoices = SalesInvoice.objects.filter(
        organization=org,
        status="posted",
        date__range=(start_date, end_date),
    )
    revenue = invoices.aggregate(total=Sum("total_amount")).get("total") or Decimal("0")
    cylinders_sold = (
        SalesInvoiceLine.objects.filter(
            invoice__in=invoices,
            cylinder_sku__state=CylinderSKU.STATE_FILLED,
        ).aggregate(total=Sum("quantity")).get("total")
        or Decimal("0")
    )
    empties_collected = invoices.aggregate(total=Sum("empty_cylinders_collected")).get("total") or 0

    return {
        "revenue": revenue,
        "cylinders_sold": cylinders_sold,
        "empties_collected": empties_collected,
        "pending_deliveries": 0,  # placeholder until delivery module is wired
    }


def revenue_expense_trend(org: Organization, months: int = 6):
    today = timezone.now().date().replace(day=1)
    data = []
    for idx in range(months):
        month_start = (today.replace(day=1) - timedelta(days=idx * 30)).replace(day=1)
        month_end = (month_start + timedelta(days=31)).replace(day=1) - timedelta(days=1)
        invoices = SalesInvoice.objects.filter(
            organization=org,
            status="posted",
            date__range=(month_start, month_end),
        )
        revenue = invoices.aggregate(total=Sum("total_amount")).get("total") or Decimal("0")
        noc_total = (
            NocPurchase.objects.filter(
                organization=org,
                status=NocPurchase.STATUS_POSTED,
                date__range=(month_start, month_end),
            ).aggregate(total=Sum("total_amount")).get("total")
            or Decimal("0")
        )
        logistics_total = (
            LogisticsTrip.objects.filter(
                organization=org,
                status="posted",
                date__range=(month_start, month_end),
            ).aggregate(total=Sum("cost")).get("total")
            or Decimal("0")
        )
        total_expenses = noc_total + logistics_total
        data.append(
            {
                "month": month_start.strftime("%Y-%m"),
                "revenue": revenue,
                "expenses": total_expenses,
                "net_profit": revenue - total_expenses,
            }
        )
    return list(reversed(data))


def profit_and_loss(org: Organization, start_date: date, end_date: date) -> Dict:
    lines = (
        JournalLine.objects.filter(
            journal__organization=org,
            journal__status="posted",
            journal__journal_date__range=(start_date, end_date),
        )
        .select_related("account", "account__account_type")
        .all()
    )
    totals = defaultdict(Decimal)
    for line in lines:
        nature = line.account.account_type.nature
        amount = Decimal(line.debit_amount or 0) - Decimal(line.credit_amount or 0)
        totals[nature] += amount

    revenue = -totals.get("income", Decimal("0"))
    expenses = totals.get("expense", Decimal("0"))
    cogs = totals.get("asset", Decimal("0"))  # inventory consumption proxy
    logistics = totals.get("liability", Decimal("0"))  # crude allocation

    return {
        "revenue": revenue,
        "cogs": cogs,
        "logistics": logistics,
        "other_expenses": expenses - logistics,
        "net_profit": revenue - expenses - cogs,
    }
