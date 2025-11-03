import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from accounting.models import (
    AccountType,
    AccountingPeriod,
    ChartOfAccount,
    FiscalYear,
    Journal,
    JournalLine,
    JournalType,
)
from usermanagement.models import Organization, UserOrganization


@pytest.mark.django_db
def test_voucher_list_and_detail_views(client, admin_user):
    # Organization and user setup
    org = Organization.objects.create(name="Test Org", code="TEST", type="company")
    admin_user.is_superuser = True
    admin_user.organization = org
    admin_user.save()
    UserOrganization.objects.create(user=admin_user, organization=org, is_active=True)
    client.force_login(admin_user)

    # Minimal accounting master data
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
        fiscal_year_prefix=False,
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
    at_ast = AccountType.objects.create(
        code="AST",
        name="Asset",
        nature="asset",
        classification="asset",
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
        account_type=at_ast,
        account_code="1000",
        account_name="Cash",
        created_by=admin_user,
        updated_by=admin_user,
    )

    # Create a balanced draft journal (voucher)
    j = Journal.objects.create(
        organization=org,
        journal_type=jt,
        period=period,
        journal_date=datetime.date(2025, 1, 15),
        description="Test voucher",
        status="draft",
        created_by=admin_user,
        updated_by=admin_user,
    )
    JournalLine.objects.create(
        journal=j,
        line_number=10,
        account=debit_acct,
        description="Debit line",
        debit_amount=1000,
        credit_amount=0,
        created_by=admin_user,
        updated_by=admin_user,
    )
    JournalLine.objects.create(
        journal=j,
        line_number=20,
        account=credit_acct,
        description="Credit line",
        debit_amount=0,
        credit_amount=1000,
        created_by=admin_user,
        updated_by=admin_user,
    )
    # Update header totals
    j.update_totals()
    j.save()

    # List view
    resp = client.get(reverse("accounting:voucher_list"))
    assert resp.status_code == 200
    assert b"Voucher Entries" in resp.content

    # Detail view
    resp = client.get(reverse("accounting:voucher_detail", kwargs={"pk": j.pk}))
    assert resp.status_code == 200
    assert b"Voucher" in resp.content


@pytest.mark.django_db
def test_voucher_post_success(client, admin_user):
    org = Organization.objects.create(name="Test Org", code="TEST", type="company")
    admin_user.is_superuser = True
    admin_user.organization = org
    admin_user.save()
    UserOrganization.objects.create(user=admin_user, organization=org, is_active=True)
    client.force_login(admin_user)

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
    at = AccountType.objects.create(
        code="EXP",
        name="Expense",
        nature="expense",
        classification="expense",
        display_order=1,
        created_by=admin_user,
        updated_by=admin_user,
    )
    debit_acct = ChartOfAccount.objects.create(
        organization=org,
        account_type=at,
        account_code="5000",
        account_name="Expense",
        created_by=admin_user,
        updated_by=admin_user,
    )
    credit_acct = ChartOfAccount.objects.create(
        organization=org,
        account_type=at,
        account_code="1000",
        account_name="Cash",
        created_by=admin_user,
        updated_by=admin_user,
    )
    j = Journal.objects.create(
        organization=org,
        journal_type=jt,
        period=period,
        journal_date=datetime.date(2025, 1, 20),
        description="Ready to post",
        status="draft",
        created_by=admin_user,
        updated_by=admin_user,
    )
    JournalLine.objects.create(
        journal=j,
        line_number=10,
        account=debit_acct,
        debit_amount=200,
        credit_amount=0,
        created_by=admin_user,
        updated_by=admin_user,
    )
    JournalLine.objects.create(
        journal=j,
        line_number=20,
        account=credit_acct,
        debit_amount=0,
        credit_amount=200,
        created_by=admin_user,
        updated_by=admin_user,
    )
    j.update_totals()
    j.save()

    post_url = reverse("accounting:voucher_post", kwargs={"pk": j.pk})
    resp = client.post(post_url)
    assert resp.status_code in (301, 302)
    j.refresh_from_db()
    assert j.status == "posted"


@pytest.mark.django_db
def test_voucher_edit_redirect_when_posted(client, admin_user):
    org = Organization.objects.create(name="Test Org", code="TEST", type="company")
    admin_user.is_superuser = True
    admin_user.organization = org
    admin_user.save()
    UserOrganization.objects.create(user=admin_user, organization=org, is_active=True)
    client.force_login(admin_user)

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
    )
    j = Journal.objects.create(
        organization=org,
        journal_type=jt,
        period=period,
        journal_date=datetime.date(2025, 1, 10),
        description="Already posted",
        status="posted",
        created_by=admin_user,
        updated_by=admin_user,
    )

    edit_url = reverse("accounting:voucher_edit", kwargs={"pk": j.pk})
    resp = client.get(edit_url)
    # Should redirect to detail if posted
    assert resp.status_code in (301, 302)


@pytest.mark.django_db
def test_voucher_duplicate_and_delete(client, admin_user):
    org = Organization.objects.create(name="Test Org", code="TEST", type="company")
    admin_user.is_superuser = True
    admin_user.organization = org
    admin_user.save()
    UserOrganization.objects.create(user=admin_user, organization=org, is_active=True)
    client.force_login(admin_user)

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
    )
    at = AccountType.objects.create(
        code="EXP",
        name="Expense",
        nature="expense",
        classification="expense",
        display_order=1,
        created_by=admin_user,
        updated_by=admin_user,
    )
    debit_acct = ChartOfAccount.objects.create(
        organization=org,
        account_type=at,
        account_code="5000",
        account_name="Expense",
        created_by=admin_user,
        updated_by=admin_user,
    )
    credit_acct = ChartOfAccount.objects.create(
        organization=org,
        account_type=at,
        account_code="1000",
        account_name="Cash",
        created_by=admin_user,
        updated_by=admin_user,
    )
    j = Journal.objects.create(
        organization=org,
        journal_type=jt,
        period=period,
        journal_date=datetime.date(2025, 1, 12),
        description="Duplicate me",
        status="draft",
        created_by=admin_user,
        updated_by=admin_user,
    )
    JournalLine.objects.create(
        journal=j,
        line_number=10,
        account=debit_acct,
        debit_amount=50,
        credit_amount=0,
        created_by=admin_user,
        updated_by=admin_user,
    )
    JournalLine.objects.create(
        journal=j,
        line_number=20,
        account=credit_acct,
        debit_amount=0,
        credit_amount=50,
        created_by=admin_user,
        updated_by=admin_user,
    )
    j.update_totals()
    j.save()

    # Duplicate via POST
    dup_url = reverse("accounting:voucher_duplicate", kwargs={"pk": j.pk})
    resp = client.post(dup_url)
    assert resp.status_code in (301, 302)

    # The newest journal should be the duplicate in draft status
    new_j = Journal.objects.exclude(pk=j.pk).order_by("-created_at").first()
    assert new_j is not None
    assert new_j.status == "draft"
    assert new_j.lines.count() == j.lines.count()

    # Delete original
    del_url = reverse("accounting:voucher_delete", kwargs={"pk": j.pk})
    resp = client.post(del_url)
    assert resp.status_code in (301, 302)
    assert not Journal.objects.filter(pk=j.pk).exists()
