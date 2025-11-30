from __future__ import annotations

from types import SimpleNamespace
from decimal import Decimal

import pytest

from accounting.services.inventory_posting_service import InventoryPostingService
from accounting.services.journal_entry_service import JournalEntryService
from Inventory.models import InventoryItem

pytestmark = pytest.mark.django_db


class _StubApprovalManager:
    def __init__(self):
        self.called_with = None

    def get_or_create(self, journal, approver):
        self.called_with = (journal, approver)
        return (SimpleNamespace(), True)


def test_journal_approval_stamps_user(monkeypatch):
    # Prepare a stub journal and user
    journal = SimpleNamespace(
        status="awaiting_approval",
        approved_by=None,
        approved_at=None,
        updated_by=None,
        approvals=SimpleNamespace(exists=lambda: False),
        save=lambda update_fields=None: None,
    )
    user = SimpleNamespace(has_perm=lambda perm: True, username="approver")

    stub_approval_mgr = _StubApprovalManager()
    monkeypatch.setattr("accounting.services.journal_entry_service.Approval", SimpleNamespace(objects=stub_approval_mgr))
    monkeypatch.setattr("accounting.services.journal_entry_service.log_audit_event", lambda *args, **kwargs: None)

    service = JournalEntryService(user=user, organization=None)  # type: ignore[arg-type]

    service.approve(journal)  # type: ignore[arg-type]

    assert journal.status == "approved"
    assert journal.approved_by is user
    assert journal.approved_at is not None
    assert stub_approval_mgr.called_with == (journal, user)


def test_inventory_posting_weighted_average_and_issue(monkeypatch):
    # Track created objects
    created_stock = []
    # Patch transaction.atomic to avoid DB connections in this unit-test path
    from contextlib import contextmanager

    @contextmanager
    def noop_atomic():
        yield

    monkeypatch.setattr(
        "accounting.services.inventory_posting_service.transaction.atomic", noop_atomic
    )

    class StubItem:
        def __init__(self):
            self.quantity_on_hand = Decimal("0")
            self.unit_cost = Decimal("0")

        def save(self, update_fields=None):
            return None

    class StubInventoryManager:
        def __init__(self):
            self.item = StubItem()

        def get_or_create(self, **kwargs):
            return self.item, True

    class StubStockManager:
        def create(self, **kwargs):
            created_stock.append(kwargs)
            return SimpleNamespace(**kwargs)

    monkeypatch.setattr("accounting.services.inventory_posting_service.InventoryItem", SimpleNamespace(objects=StubInventoryManager()))
    monkeypatch.setattr("accounting.services.inventory_posting_service.StockLedger", SimpleNamespace(objects=StubStockManager()))

    product = SimpleNamespace(inventory_account="INV", expense_account="COGS")
    warehouse = SimpleNamespace()
    grir_account = "GRIR"

    service = InventoryPostingService(organization=None)

    # Receipt 10 units @ 5
    receipt = service.record_receipt(
        product=product,
        warehouse=warehouse,
        quantity=Decimal("10"),
        unit_cost=Decimal("5"),
        grir_account=grir_account,
        reference_id="PI-1",
    )
    assert receipt.unit_cost == Decimal("5")
    assert receipt.total_cost == Decimal("50")
    assert receipt.debit_account == "INV"
    assert receipt.credit_account == "GRIR"

    # Issue 4 units -> uses weighted avg 5
    issue = service.record_issue(
        product=product,
        warehouse=warehouse,
        quantity=Decimal("4"),
        reference_id="SI-1",
        cogs_account="COGS",
    )
    assert issue.unit_cost == Decimal("5")
    assert issue.total_cost == Decimal("20")
    assert issue.debit_account == "COGS"
    assert issue.credit_account == "INV"

    # After receipt and issue, remaining on-hand should be 6 units @ 5
    item = InventoryItem.objects.get(product=product, warehouse=warehouse)
    assert item.quantity_on_hand == Decimal("6")
    assert item.unit_cost == Decimal("5")
    # Stock ledger was created twice (receipt + issue)
    assert len(created_stock) == 2
