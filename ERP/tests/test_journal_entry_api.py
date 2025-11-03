import datetime
import json

import pytest
from django.urls import reverse

from accounting.models import (
    AccountType,
    AccountingPeriod,
    ChartOfAccount,
    CostCenter,
    FiscalYear,
    Journal,
    JournalType,
)
from usermanagement.models import Organization, UserOrganization


def _create_master_data(admin_user):
    org = Organization.objects.create(name="Test Org", code="TEST", type="company")
    admin_user.is_superuser = True
    admin_user.organization = org
    admin_user.save()
    UserOrganization.objects.create(user=admin_user, organization=org, is_active=True)

    fy = FiscalYear.objects.create(
        organization=org,
        code="FY25",
        name="FY 2025",
        start_date=datetime.date(2025, 1, 1),
        end_date=datetime.date(2025, 12, 31),
        is_current=True,
        created_by=admin_user,
    )
    period = AccountingPeriod.objects.create(
        fiscal_year=fy,
        period_number=1,
        name="Jan 2025",
        start_date=datetime.date(2025, 1, 1),
        end_date=datetime.date(2025, 1, 31),
        status="open",
        created_by=admin_user,
    )
    jt = JournalType.objects.create(
        organization=org,
        code="GJ",
        name="General Journal",
        created_by=admin_user,
        updated_by=admin_user,
        auto_numbering_prefix="GJ-",
    )
    at_exp = AccountType.objects.create(
        code="EXP",
        name="Expense",
        nature="expense",
        classification="expense",
        display_order=1,
        created_by=admin_user,
        updated_by=admin_user,
    )
    at_inc = AccountType.objects.create(
        code="INC",
        name="Income",
        nature="income",
        classification="income",
        display_order=2,
        created_by=admin_user,
        updated_by=admin_user,
    )
    debit_acct = ChartOfAccount.objects.create(
        organization=org,
        account_type=at_exp,
        account_code="5000",
        account_name="Expense",
        created_by=admin_user,
        updated_by=admin_user,
    )
    credit_acct = ChartOfAccount.objects.create(
        organization=org,
        account_type=at_inc,
        account_code="4000",
        account_name="Income",
        created_by=admin_user,
        updated_by=admin_user,
    )
    cost_center = CostCenter.objects.create(
        organization=org,
        code="MAIN",
        name="Main",
        is_active=True,
    )
    return {
        "organization": org,
        "period": period,
        "journal_type": jt,
        "debit_account": debit_acct,
        "credit_account": credit_acct,
        "cost_center": cost_center,
    }


def _base_payload(master_data):
    debit = master_data["debit_account"]
    credit = master_data["credit_account"]
    cost_center = master_data["cost_center"]
    return {
        "header": {
            "date": "2025-01-15",
            "currency": "USD",
            "exRate": 1,
            "creditDays": 0,
            "reference": "REF-001",
            "description": "API journal entry",
            "branch": "Main",
            "udf_invoice": "INV-001",
        },
        "rows": [
            {
                "account": f"{debit.account_code} - {debit.account_name}",
                "accountId": debit.pk,
                "accountCode": debit.account_code,
                "narr": "Debit line",
                "dr": 200,
                "cr": 0,
                "costCenter": cost_center.code,
                "costCenterId": cost_center.pk,
            },
            {
                "account": f"{credit.account_code} - {credit.account_name}",
                "accountId": credit.pk,
                "accountCode": credit.account_code,
                "narr": "Credit line",
                "dr": 0,
                "cr": 200,
            },
        ],
        "udfHeaderDefs": [
            {"id": "udf_invoice", "label": "Invoice No.", "type": "text", "required": True},
        ],
        "udfLineDefs": [],
        "charges": [
            {"id": "charge1", "label": "Freight", "mode": "amount", "value": 25, "sign": 1},
        ],
        "notes": "API journal entry",
        "numbering": {"prefix": {"Journal": "JV"}, "nextSeq": {"Journal": 1}, "width": 4},
        "meta": {"journalTypeCode": "GJ"},
    }


@pytest.mark.django_db
def test_journal_entry_save_submit_approve(client, admin_user):
    master = _create_master_data(admin_user)
    client.force_login(admin_user)

    payload = _base_payload(master)

    save_url = reverse("accounting:journal_save_draft")
    submit_url = reverse("accounting:journal_submit")
    approve_url = reverse("accounting:journal_approve")
    
    # Save draft
    resp = client.post(save_url, data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    journal_payload = data["journal"]
    journal_id = journal_payload["id"]
    journal = Journal.objects.get(pk=journal_id)
    assert journal.status == "draft"
    assert journal.header_udf_data.get("udf_invoice") == "INV-001"
    assert journal.charges_data and journal.charges_data[0]["label"] == "Freight"
    assert journal.lines.count() == 2

    # Submit
    payload["journalId"] = journal_id
    resp = client.post(submit_url, data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    journal.refresh_from_db()
    assert journal.status == "awaiting_approval"

    # Approve
    resp = client.post(approve_url, data=json.dumps({"journalId": journal_id}), content_type="application/json")
    assert resp.status_code == 200
    journal.refresh_from_db()
    assert journal.status == "approved"

    # Fetch detail
    resp = client.get(reverse("accounting:journal_entry_data", kwargs={"pk": journal_id}))
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["ok"] is True
    returned = detail["journal"]
    assert returned["status"] == "approved"
    assert returned["header"]["currency"] == "USD"
    assert returned["charges"][0]["label"] == "Freight"


@pytest.mark.django_db
def test_journal_entry_validation_errors(client, admin_user):
    master = _create_master_data(admin_user)
    client.force_login(admin_user)

    bad_payload = _base_payload(master)
    # Remove credit line account information to trigger validation error
    bad_payload["rows"][1]["account"] = ""
    bad_payload["rows"][1]["accountId"] = None
    bad_payload["rows"][1]["accountCode"] = ""

    save_url = reverse("accounting:journal_save_draft")
    resp = client.post(save_url, data=json.dumps(bad_payload), content_type="application/json")
    assert resp.status_code == 400
    data = resp.json()
    assert data["ok"] is False
    assert "errors" in data.get("details", {})
    assert any("Line" in err for err in data["details"]["errors"])
