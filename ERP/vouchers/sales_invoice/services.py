"""
Service layer for HTMX Sales Invoice.

This module encapsulates business rules for manipulating
`SalesInvoiceDraft` objects and their associated lines and receipts.
All calculations are performed on the server to ensure that totals
remain consistent across UI interactions, submission and posting.

The service exposes helper methods for loading or creating drafts,
parsing incoming POST data to update drafts, recalculating totals,
converting dates between the Nepali and Gregorian calendars, and
generating the next invoice number. It also provides simple lookup
collections for dropdowns; these should ideally pull from real
models but are stubbed here for demonstration.
"""

from __future__ import annotations

import decimal
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Tuple

from django.db import transaction
from django.shortcuts import get_object_or_404

from .models import (
    SalesInvoiceDraft,
    SalesInvoiceDraftLine,
    SalesInvoiceDraftReceipt,
)

try:
    # The calendar conversion utilities are optional; they exist in ERP.utils.calendars
    from ERP.utils.calendars import bs_to_ad, ad_to_bs_string
except Exception:
    # Fallback stubs; if not available the service will not convert between BS and AD.
    def bs_to_ad(bs_str: str) -> Optional[Any]:
        return None

    def ad_to_bs_string(date) -> Optional[str]:
        return None


class SalesInvoiceDraftService:
    """Service for manipulating and recalculating SalesInvoiceDrafts."""

    VAT_RATE = Decimal("13")  # 13% default VAT

    @classmethod
    def load_or_create(cls, user: Optional[Any], draft_id: Optional[str]) -> SalesInvoiceDraft:
        """Load an existing draft for the user or create a new one.

        If `draft_id` is provided it will attempt to fetch the draft. If
        not found or not provided, a new draft is created. Drafts tied to
        a specific user ensure that accidental sharing across sessions is
        avoided.
        """
        if draft_id:
            try:
                draft = SalesInvoiceDraft.objects.get(pk=draft_id)
                # Optional: verify user ownership
                if user and draft.user and draft.user != user:
                    raise PermissionError("Draft does not belong to current user")
                return draft
            except SalesInvoiceDraft.DoesNotExist:
                pass
        return SalesInvoiceDraft.objects.create(user=user)

    # Lookup stubs. Replace with real queries against your own models.
    @classmethod
    def get_lookup_data(cls) -> Dict[str, List[Dict[str, Any]]]:
        """Return static lookups for dropdown fields.

        In a production system these would query Customers, Chart of
        Accounts, Agents, Warehouses, Items, etc. For now we return
        placeholder data for demonstration.
        """
        return {
            "buyers": [
                {"id": 1, "name": "ABC Traders"},
                {"id": 2, "name": "XYZ Suppliers"},
            ],
            "sales_accounts": [
                {"id": 10, "name": "Sales - Local"},
                {"id": 11, "name": "Sales - Export"},
            ],
            "agents": [
                {"id": 1, "name": "Agent Ram"},
                {"id": 2, "name": "Agent Sita"},
            ],
            "agent_areas": [
                {"id": 1, "name": "Kathmandu"},
                {"id": 2, "name": "Birgunj"},
            ],
            "orders": [
                {"id": "SO-101", "display": "SO-101 (Pending)"},
                {"id": "SO-102", "display": "SO-102 (Pending)"},
            ],
            "terms": [
                {"id": 1, "name": "Trade Terms"},
                {"id": 2, "name": "Standard Terms"},
            ],
            "units": ["Nos", "Kg", "Ltr", "Bag", "Box"],
            "godowns": [
                {"id": 1, "name": "Main Store"},
                {"id": 2, "name": "Secondary Store"},
            ],
            "receipt_ledgers": [
                {"id": 1, "name": "Cash"},
                {"id": 2, "name": "NIC Asia Bank"},
                {"id": 3, "name": "NMB Bank"},
            ],
            "items": [
                {"id": 1, "name": "Cement (50kg)", "code": "HS-2523", "unit": "Bag", "default_rate": 950, "vat": True},
                {"id": 2, "name": "Rod (12mm)", "code": "HS-7214", "unit": "Kg", "default_rate": 125, "vat": True},
                {"id": 3, "name": "Transport Charge", "code": "SRV-001", "unit": "Nos", "default_rate": 500, "vat": False},
            ],
            "payment_modes": ["Credit", "Cash", "Bank", "Other"],
        }

    @classmethod
    def update_from_post(cls, draft: SalesInvoiceDraft, post_data: Dict[str, Any]) -> None:
        """Update a draft based on the incoming POST data.

        This method reads scalar header fields, updates or creates line
        objects according to names following the pattern
        `line_<field>__<line_id>` and similarly for receipts. Fields not
        present in the POST data are left unchanged.
        """
        # Header scalar fields
        scalar_fields = [
            "invoice_prefix",
            "invoice_no",
            "invoice_series_id",
            "fiscal_year",
            "ref_no",
            "date_bs",
            "date_ad",
            "due_days",
            "buyer_id",
            "sales_account_id",
            "payment_mode",
            "order_ref_id",
            "agent_id",
            "agent_area_id",
            "terms_id",
            "narration",
            "header_discount_value",
            "header_discount_type",
            "rounding_amount",
        ]
        for field in scalar_fields:
            if field in post_data:
                value = post_data.get(field)
                # Cast numeric fields accordingly
                if field in {"invoice_no", "invoice_series_id", "buyer_id", "sales_account_id", "agent_id", "agent_area_id", "terms_id"}:
                    draft.__setattr__(field, int(value) if value else None)
                elif field in {"header_discount_value", "rounding_amount"}:
                    draft.__setattr__(field, Decimal(value) if value else Decimal("0"))
                elif field == "due_days":
                    draft.due_days = int(value) if value else 0
                elif field == "date_ad":
                    # date field; handle empty string
                    draft.date_ad = value or None
                else:
                    draft.__setattr__(field, value or None)

        # Lines: group fields by line id
        # A line field name looks like 'line_item_id__<uuid>'
        line_updates: Dict[str, Dict[str, Any]] = {}
        for key, value in post_data.items():
            if key.startswith("line_") and "__" in key:
                field, ident = key.split("__", 1)
                line_updates.setdefault(ident, {})[field[len("line_"):]] = value
        # Update existing lines and create new ones if necessary
        for line in list(draft.lines.all()):
            data = line_updates.pop(str(line.id), None)
            if not data:
                continue
            cls._update_line_from_data(line, data)
        # Remaining keys correspond to new lines (IDs not found yet). Skip for now as lines are only
        # created via add_line.

        # Receipts
        receipt_updates: Dict[str, Dict[str, Any]] = {}
        for key, value in post_data.items():
            if key.startswith("rcpt_") and "__" in key:
                field, ident = key.split("__", 1)
                receipt_updates.setdefault(ident, {})[field[len("rcpt_"):]] = value
        for rcpt in list(draft.receipts.all()):
            data = receipt_updates.pop(str(rcpt.id), None)
            if not data:
                continue
            if "account" in data:
                acc = data.get("account")
                rcpt.account_id = int(acc) if acc else None
            if "amount" in data:
                rcpt.amount = Decimal(data.get("amount") or "0")
            if "note" in data:
                rcpt.note = data.get("note") or None
            rcpt.save()

    @classmethod
    def _update_line_from_data(cls, line: SalesInvoiceDraftLine, data: Dict[str, str]) -> None:
        """Update a single draft line given parsed data."""
        if "item_id" in data:
            line.item_id = int(data["item_id"]) if data["item_id"] else None
        if "description" in data:
            line.description = data["description"] or None
        if "hs_code" in data:
            line.hs_code = data["hs_code"] or None
        if "qty" in data:
            line.qty = Decimal(data["qty"] or "0")
        if "unit_id" in data:
            line.unit_id = data["unit_id"] or "Nos"
        if "godown_id" in data:
            line.godown_id = int(data["godown_id"]) if data["godown_id"] else None
        if "rate" in data:
            line.rate = Decimal(data["rate"] or "0")
        if "disc_type" in data:
            line.disc_type = data["disc_type"] or "none"
        if "disc_value" in data:
            line.disc_value = Decimal(data["disc_value"] or "0")
        if "vat_yes" in data:
            line.vat_applicable = True if data["vat_yes"] in ("yes", "True", "true", True) else False
        line.save()

    @classmethod
    def add_line(cls, draft: SalesInvoiceDraft) -> None:
        """Append a new empty line to the draft."""
        sn = draft.lines.count() + 1
        SalesInvoiceDraftLine.objects.create(draft=draft, sn=sn)

    @classmethod
    def delete_line(cls, draft: SalesInvoiceDraft, line_id: str) -> None:
        """Remove the line with the given identifier and resequence SNs."""
        try:
            line = draft.lines.get(pk=line_id)
            line.delete()
            # Resequence the remaining lines
            for idx, l in enumerate(draft.lines.order_by("sn", "id"), start=1):
                if l.sn != idx:
                    l.sn = idx
                    l.save(update_fields=["sn"])
        except SalesInvoiceDraftLine.DoesNotExist:
            return

    @classmethod
    def add_receipt(cls, draft: SalesInvoiceDraft) -> None:
        """Add a blank receipt row."""
        SalesInvoiceDraftReceipt.objects.create(draft=draft)

    @classmethod
    def delete_receipt(cls, draft: SalesInvoiceDraft, receipt_id: str) -> None:
        """Delete a receipt row."""
        try:
            rcpt = draft.receipts.get(pk=receipt_id)
            rcpt.delete()
        except SalesInvoiceDraftReceipt.DoesNotExist:
            return

    @classmethod
    def recalc(cls, draft: SalesInvoiceDraft) -> None:
        """Recalculate all derived fields on the draft.

        This method computes per-line net rates, line totals, taxable and
        VAT amounts, splits totals into vatable and non-vatable buckets,
        applies header discounts proportionally, and derives final header
        totals including rounding and remaining balance. Results are
        persisted back onto the draft and its lines.
        """
        # Convert to decimals for precision
        vat_rate = cls.VAT_RATE / Decimal("100")

        sub_total = Decimal("0")
        nonvat_taxable_sum = Decimal("0")
        vat_taxable_sum = Decimal("0")
        nonvat_disc_sum = Decimal("0")
        vat_disc_sum = Decimal("0")
        vat_amount_sum = Decimal("0")

        for line in draft.lines.all().order_by("sn", "id"):
            qty = line.qty or Decimal("0")
            rate = line.rate or Decimal("0")
            gross = qty * rate
            sub_total += gross
            # line discount
            disc_amt = Decimal("0")
            if line.disc_type == "pct":
                disc_amt = gross * (line.disc_value / Decimal("100"))
            elif line.disc_type == "amt":
                disc_amt = line.disc_value
            disc_amt = max(Decimal("0"), min(disc_amt, gross))
            taxable = gross - disc_amt
            vat = Decimal("0")
            line_total = taxable
            if line.vat_applicable:
                vat = taxable * vat_rate
                line_total = taxable + vat
                vat_taxable_sum += taxable
                vat_disc_sum += disc_amt
                vat_amount_sum += vat
            else:
                nonvat_taxable_sum += taxable
                nonvat_disc_sum += disc_amt
            # update line computed fields
            line.line_taxable = taxable
            line.line_vat = vat
            line.line_total = line_total
            line.net_rate = (line_total / qty) if qty else Decimal("0")
            line.save(update_fields=["line_taxable", "line_vat", "line_total", "net_rate"])

        # Header discount after line-level discounts
        discount_value = draft.header_discount_value or Decimal("0")
        hdr_disc = Decimal("0")
        taxable_before_hdr = nonvat_taxable_sum + vat_taxable_sum
        if taxable_before_hdr > 0:
            if draft.header_discount_type == "pct":
                hdr_disc = taxable_before_hdr * (discount_value / Decimal("100"))
            else:
                hdr_disc = discount_value
            hdr_disc = max(Decimal("0"), min(hdr_disc, taxable_before_hdr))
        # Allocate header discount proportionally
        share_vat = (vat_taxable_sum / taxable_before_hdr) if taxable_before_hdr > 0 else Decimal("0")
        hdr_disc_vat = hdr_disc * share_vat
        hdr_disc_non = hdr_disc - hdr_disc_vat

        total_nonvat_amount = max(Decimal("0"), nonvat_taxable_sum - hdr_disc_non)
        total_vatable_amount = max(Decimal("0"), vat_taxable_sum - hdr_disc_vat)

        taxable_amount = total_vatable_amount
        vat_amount = taxable_amount * vat_rate
        grand_total = total_nonvat_amount + total_vatable_amount + vat_amount + (draft.rounding_amount or Decimal("0"))

        # Paid and remaining balance
        paid_total = sum((rcpt.amount or Decimal("0")) for rcpt in draft.receipts.all())
        remaining_balance = grand_total - paid_total

        # Amount in words (simple conversion)
        draft.amount_in_words = cls._number_to_words(grand_total) + " rupees only."

        # Persist computed totals on draft
        draft.sub_total = sub_total
        draft.nonvat_amount = nonvat_taxable_sum
        draft.nonvat_discount = nonvat_disc_sum + hdr_disc_non
        draft.total_nonvat_amount = total_nonvat_amount
        draft.vatable_amount = vat_taxable_sum
        draft.vatable_discount = vat_disc_sum + hdr_disc_vat
        draft.total_vatable_amount = total_vatable_amount
        draft.taxable_amount = taxable_amount
        draft.vat_amount = vat_amount
        draft.grand_total = grand_total
        draft.remaining_balance = remaining_balance
        draft.save(
            update_fields=[
                "sub_total",
                "nonvat_amount",
                "nonvat_discount",
                "total_nonvat_amount",
                "vatable_amount",
                "vatable_discount",
                "total_vatable_amount",
                "taxable_amount",
                "vat_amount",
                "grand_total",
                "amount_in_words",
                "remaining_balance",
            ]
        )

    @classmethod
    def convert_bs_to_ad(cls, draft: SalesInvoiceDraft) -> None:
        """Convert BS date to AD using available calendar utils and set date_ad."""
        if draft.date_bs:
            try:
                ad_date = bs_to_ad(draft.date_bs)
                if ad_date:
                    draft.date_ad = ad_date
                    draft.save(update_fields=["date_ad"])
            except Exception:
                pass

    @classmethod
    def convert_ad_to_bs(cls, draft: SalesInvoiceDraft) -> None:
        """Convert AD date to BS and set date_bs if utils are available."""
        if draft.date_ad:
            try:
                bs_str = ad_to_bs_string(draft.date_ad)
                if bs_str:
                    draft.date_bs = bs_str
                    draft.save(update_fields=["date_bs"])
            except Exception:
                pass

    @classmethod
    def get_next_invoice_number(cls, draft: SalesInvoiceDraft) -> None:
        """Assign the next invoice number for the given prefix/series.

        This stub simply increments the highest existing invoice number for the
        given prefix found across drafts. In a real implementation this
        should delegate to DocumentSequenceConfig or an atomic counter.
        """
        if draft.invoice_no:
            return
        # naive: find max invoice_no for same prefix and add 1
        max_no = (
            SalesInvoiceDraft.objects.filter(invoice_prefix=draft.invoice_prefix, invoice_no__isnull=False)
            .order_by("-invoice_no")
            .values_list("invoice_no", flat=True)
            .first()
        ) or 0
        draft.invoice_no = max_no + 1
        draft.save(update_fields=["invoice_no"])

    @staticmethod
    def _number_to_words(n: Decimal) -> str:
        """Convert a number into English words (supports up to billions)."""
        n_int = int(n.quantize(Decimal("1"), rounding=decimal.ROUND_HALF_UP))
        if n_int == 0:
            return "Zero"
        ones = [
            "",
            "One",
            "Two",
            "Three",
            "Four",
            "Five",
            "Six",
            "Seven",
            "Eight",
            "Nine",
            "Ten",
            "Eleven",
            "Twelve",
            "Thirteen",
            "Fourteen",
            "Fifteen",
            "Sixteen",
            "Seventeen",
            "Eighteen",
            "Nineteen",
        ]
        tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

        def chunk_to_words(x: int) -> str:
            s = ""
            if x >= 100:
                s += ones[x // 100] + " Hundred "
                x = x % 100
            if x >= 20:
                s += tens[x // 10] + " "
                x = x % 10
            if x > 0:
                s += ones[x] + " "
            return s.strip()

        parts = [
            (1_000_000_000, "Billion"),
            (1_000_000, "Million"),
            (1_000, "Thousand"),
        ]
        out = []
        for value, name in parts:
            if n_int >= value:
                out.append(chunk_to_words(n_int // value) + " " + name)
                n_int %= value
        if n_int > 0:
            out.append(chunk_to_words(n_int))
        return " ".join(out).strip()
