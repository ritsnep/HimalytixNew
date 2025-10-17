from django.test import TestCase
import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model

# Create your tests here.
pytestmark = pytest.mark.django_db()
from accounting.models import (
    Organization,
    AccountingPeriod,
    FiscalYear,
    JournalType,
    ChartOfAccount,
    AccountType,
    Journal,
    JournalLine,
)
from accounting.services import post_journal, close_period

User = get_user_model()

@pytest.fixture
def org():
    return Organization.objects.create(name="Org", code="ORG", type="company")

@pytest.fixture
def user(org):
    return User.objects.create_user(username="u", password="p", role="admin", organization=org)

@pytest.fixture
def fiscal_year(org):
    return FiscalYear.objects.create(
        organization=org,
        code="FY1",
        name="2024",
        start_date="2024-01-01",
        end_date="2024-12-31",
    )

@pytest.fixture
def period(fiscal_year, user):
    return AccountingPeriod.objects.create(
        fiscal_year=fiscal_year,
        period_number=1,
        name="P1",
        start_date="2024-01-01",
        end_date="2024-01-31",
        created_by=user,
    )

@pytest.fixture
def account_type(org):
    return AccountType.objects.create(
        code="AST1",
        name="Cash",
        nature="asset",
        classification="current",
        display_order=1,
        created_by=None,
    )

@pytest.fixture
def accounts(org, account_type):
    a1 = ChartOfAccount.objects.create(
        organization=org,
        account_type=account_type,
        account_code="1000",
        account_name="Cash",
    )
    a2 = ChartOfAccount.objects.create(
        organization=org,
        account_type=account_type,
        account_code="2000",
        account_name="Bank",
    )
    return a1, a2

@pytest.fixture
def journal_type(org):
    return JournalType.objects.create(
        organization=org,
        code="GEN",
        name="General",
        auto_numbering_prefix="JN",
    )


def create_journal(org, period, journal_type, accounts):
    journal = Journal.objects.create(
        organization=org,
        journal_type=journal_type,
        period=period,
        journal_date=period.start_date,
    )
    JournalLine.objects.create(journal=journal, line_number=1, account=accounts[0], debit_amount=100, credit_amount=0)
    JournalLine.objects.create(journal=journal, line_number=2, account=accounts[1], debit_amount=0, credit_amount=100)
    journal.total_debit = 100
    journal.total_credit = 100
    journal.save()
    return journal


def test_post_journal_happy_path(org, period, journal_type, accounts):
    journal = create_journal(org, period, journal_type, accounts)
    post_journal(journal)
    assert journal.status == "posted"
    assert journal.journal_number.startswith("JN")
    assert journal.lines.count() == 2
    assert journal.generalledger_set.count() == 2


def test_post_journal_unbalanced(org, period, journal_type, accounts):
    journal = Journal.objects.create(
        organization=org,
        journal_type=journal_type,
        period=period,
        journal_date=period.start_date,
    )
    JournalLine.objects.create(journal=journal, line_number=1, account=accounts[0], debit_amount=50)
    JournalLine.objects.create(journal=journal, line_number=2, account=accounts[1], credit_amount=40)
    journal.total_debit = 50
    journal.total_credit = 40
    journal.save()
    with pytest.raises(ValidationError):
        post_journal(journal)


def test_account_parent_org_validation(org, accounts, account_type):
    other_org = Organization.objects.create(name="Other", code="OTH", type="company")
    parent = ChartOfAccount.objects.create(
        organization=other_org,
        account_type=account_type,
        account_code="3000",
        account_name="Parent",
    )
    serializer_data = {
        "organization": org.id,
        "parent_account": parent.pk,
        "account_type": account_type.pk,
        "account_name": "Child",
    }
    from api.serializers import ChartOfAccountSerializer
    serializer = ChartOfAccountSerializer(data=serializer_data, context={"request": type("obj", (), {"user": type("u", (), {"organization": org})()})})
    assert not serializer.is_valid()


def test_close_period_blocks_posting(org, period, journal_type, accounts, user):
    journal = create_journal(org, period, journal_type, accounts)
    post_journal(journal)
    close_period(period, user)
    assert period.status == "closed"
    journal2 = create_journal(org, period, journal_type, accounts)
    with pytest.raises(ValidationError):
        post_journal(journal2)