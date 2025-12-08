import pytest
from django.urls import reverse
from django.utils import timezone

from reporting.models import ReportDefinition, ReportTemplate, ScheduledReport
from usermanagement.models import Organization


@pytest.fixture
def organization(db):
    return Organization.objects.create(
        name="Test Org",
        code="TST",
        type="company",
        fiscal_year_start_month=1,
        fiscal_year_start_day=1,
    )


def _auth_client(client, user, organization):
    user.organization = organization
    user.save()
    client.force_login(user)
    return client


def test_base_template_used_when_custom_disabled(settings, client, user, organization):
    settings.ENABLE_CUSTOM_REPORTS = False
    _auth_client(client, user, organization)

    ReportDefinition.objects.create(
        code="journal_report",
        name="Journal",
        organization=organization,
        base_template_name="reporting/base/journal_report.html",
        template_html="<div>Custom Layout</div>",
        is_custom_enabled=True,
    )

    resp = client.get(reverse("reporting:report_view", args=["journal_report"]))
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Custom Layout" not in body
    assert "Journal Report" in body or "journal" in body.lower()


def test_custom_template_rendered_when_enabled(settings, client, user, organization):
    settings.ENABLE_CUSTOM_REPORTS = True
    _auth_client(client, user, organization)

    ReportDefinition.objects.create(
        code="journal_report",
        name="Journal",
        organization=organization,
        base_template_name="reporting/base/journal_report.html",
        template_html="<div id='custom-flag'>Custom Layout</div>",
        is_custom_enabled=True,
    )

    resp = client.get(reverse("reporting:report_view", args=["journal_report"]))
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "custom-flag" in body


def test_designer_requires_staff(client, user, organization):
    _auth_client(client, user, organization)
    resp = client.get(reverse("reporting:report_designer", args=["journal_report"]))
    assert resp.status_code == 403


def test_designer_allows_staff_and_shows_ui(client, admin_user, organization):
    _auth_client(client, admin_user, organization)
    definition = ReportDefinition.objects.create(
        code="journal_report",
        name="Journal",
        organization=organization,
        base_template_name="reporting/base/journal_report.html",
        template_html="<div>Base</div>",
        is_custom_enabled=True,
    )
    ReportTemplate.objects.create(
        definition=definition,
        organization=None,
        name="Modern",
        description="Gallery",
        template_html="<div>Gallery</div>",
        is_gallery=True,
        is_active=True,
    )

    resp = client.get(reverse("reporting:report_designer", args=[definition.code]))
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "template-picker" in body
    assert "refresh-sample" in body


def test_template_api_includes_gallery(client, admin_user, organization):
    _auth_client(client, admin_user, organization)
    definition = ReportDefinition.objects.create(
        code="trial_balance",
        name="Trial Balance",
        organization=organization,
        base_template_name="reporting/base/trial_balance.html",
        template_html="<div>Base</div>",
        is_custom_enabled=True,
    )
    gallery = ReportTemplate.objects.create(
        definition=definition,
        organization=None,
        name="Gallery TB",
        description="Gallery layout",
        template_html="<div>Gallery</div>",
        is_gallery=True,
        is_active=True,
    )
    url = reverse("reporting:report_template_api")
    resp = client.get(f"{url}?code={definition.code}&include_gallery=1")
    assert resp.status_code == 200
    data = resp.json()
    assert any(item["id"] == gallery.id for item in data.get("gallery", []))


def test_template_api_loads_specific_gallery(client, admin_user, organization):
    _auth_client(client, admin_user, organization)
    definition = ReportDefinition.objects.create(
        code="balance_sheet",
        name="Balance Sheet",
        organization=organization,
        base_template_name="reporting/base/balance_sheet.html",
        template_html="<div>Base</div>",
        is_custom_enabled=True,
    )
    gallery = ReportTemplate.objects.create(
        definition=definition,
        organization=None,
        name="Gallery BS",
        description="Gallery layout",
        template_html="<div id='gallery-flag'>Gallery</div>",
        is_gallery=True,
        is_active=True,
    )
    url = reverse("reporting:report_template_api")
    resp = client.get(f"{url}?code={definition.code}&template_id={gallery.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "gallery-flag" in data.get("template_html", "")


def test_sample_api_returns_rows(monkeypatch, client, admin_user, organization):
    _auth_client(client, admin_user, organization)
    definition = ReportDefinition.objects.create(
        code="profit_loss",
        name="P&L",
        organization=organization,
        base_template_name="reporting/base/profit_loss.html",
        template_html="<div>Base</div>",
        is_custom_enabled=True,
    )

    def fake_context(self, definition_obj, params):
        return {"rows": [{"journal_number": "J1", "journal_date": "2024-01-01"}]}

    from reporting import services

    monkeypatch.setattr(services.ReportDataService, "build_context", fake_context, raising=True)

    url = reverse("reporting:report_sample_api")
    resp = client.get(f"{url}?code={definition.code}")
    assert resp.status_code == 200
    assert resp.json()["rows"][0]["journal_number"] == "J1"


def test_scheduled_reports_view_and_toggle(client, admin_user, organization):
    _auth_client(client, admin_user, organization)
    definition = ReportDefinition.objects.create(
        code="general_ledger",
        name="GL",
        organization=organization,
        base_template_name="reporting/base/general_ledger.html",
        template_html="<div>Base</div>",
        is_custom_enabled=True,
    )
    schedule = ScheduledReport.objects.create(
        report_definition=definition,
        report_code=definition.code,
        organization=organization,
        frequency="daily",
        format="pdf",
        next_run=timezone.now(),
        recipients=["test@example.com"],
        created_by=admin_user,
    )
    url = reverse("reporting:scheduled_reports")
    resp = client.get(url)
    assert resp.status_code == 200
    assert str(schedule.id) in resp.content.decode()

    resp = client.post(url, {"action": "toggle", "id": schedule.id})
    schedule.refresh_from_db()
    assert schedule.is_active is False


def test_report_view_uses_base_template(monkeypatch, client, admin_user, organization):
    _auth_client(client, admin_user, organization)
    definition = ReportDefinition.objects.create(
        code="trial_balance",
        name="TB",
        organization=organization,
        base_template_name="reporting/base/trial_balance.html",
        template_html="",
        is_custom_enabled=False,
    )

    def fake_context(self, definition_obj, params):
        return {
            "lines": [{"account_code": "1000", "account_name": "Cash", "account_type": "Asset", "debit_balance": 0, "credit_balance": 0}],
            "totals": {"total_debits": 0, "total_credits": 0, "difference": 0},
            "columns": [],
            "flat_rows": [],
        }

    from reporting import services

    monkeypatch.setattr(services.ReportDataService, "build_context", fake_context, raising=True)

    resp = client.get(reverse("reporting:report_view", args=[definition.code]))
    assert resp.status_code == 200
    assert "Trial Balance" in resp.content.decode()
