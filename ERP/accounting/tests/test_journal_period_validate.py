from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounting.models import AccountingPeriod, FiscalYear
from usermanagement.models import Organization, UserOrganization


class JournalPeriodValidateTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Acme Corp",
            code="ACME",
            type="company",
        )
        User = get_user_model()
        self.user = User.objects.create_user(
            username="period-user",
            password="pass123",
            role="superadmin",
            organization=self.organization,
        )
        UserOrganization.objects.create(
            user=self.user,
            organization=self.organization,
            is_active=True,
        )
        self.client.force_login(self.user)
        self.fiscal_year = FiscalYear.objects.create(
            organization=self.organization,
            code="FY24",
            name="FY 2024",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            status="open",
            is_current=True,
        )
        self.period = AccountingPeriod.objects.create(
            fiscal_year=self.fiscal_year,
            period_number=1,
            name="Jan 2024",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            status="open",
            is_current=True,
        )

    def test_valid_date_returns_open_period(self):
        url = reverse("accounting:journal_period_validate")
        resp = self.client.get(url, {"date": "2024-01-10"})
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["period"]["id"], self.period.pk)

    def test_closed_period_is_rejected(self):
        self.period.status = "closed"
        self.period.save(update_fields=["status"])
        url = reverse("accounting:journal_period_validate")
        resp = self.client.get(url, {"date": "2024-01-10"})
        self.assertEqual(resp.status_code, 400)
        payload = resp.json()
        self.assertFalse(payload["ok"])
        self.assertIn("No open accounting period", payload["error"])
