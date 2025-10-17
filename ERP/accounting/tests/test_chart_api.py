import json
import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from accounting.models import AccountType, ChartOfAccount
from usermanagement.models import Organization, UserOrganization

pytestmark = pytest.mark.django_db()

@pytest.fixture
def org():
    return Organization.objects.create(name="Org", code="ORG", type="company")

@pytest.fixture
def user(org):
    User = get_user_model()
    u = User.objects.create_user(username="u", password="p", role="superadmin")
    UserOrganization.objects.create(user=u, organization=org, is_active=True)
    return u

@pytest.fixture
def account_type():
    return AccountType.objects.create(code="AST1", name="Asset", nature="asset", classification="current", display_order=1)

@pytest.fixture
def parent_account(org, account_type):
    return ChartOfAccount.objects.create(
        organization=org,
        account_type=account_type,
        account_code="1000",
        account_name="Parent",
    )


def test_quick_create_creates_account(client, user, org, account_type, parent_account):
    client.force_login(user)
    url = reverse("accounting:chart_of_accounts_quick_create")
    resp = client.post(
        url,
        data=json.dumps({"parent_id": parent_account.pk, "name": "Child", "type": "asset"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert ChartOfAccount.objects.filter(account_name="Child", parent_account=parent_account).exists()


def test_validate_hierarchy_detects_cycle(client, user, org, account_type, parent_account):
    child = ChartOfAccount.objects.create(
        organization=org,
        account_type=account_type,
        parent_account=parent_account,
        account_code="1000.01",
        account_name="Child",
    )
    # introduce cycle without validation
    ChartOfAccount.objects.filter(pk=parent_account.pk).update(parent_account=child)
    client.force_login(user)
    url = reverse("accounting:chart_of_accounts_validate_hierarchy")
    resp = client.get(url)
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is False
    assert data["errors"]