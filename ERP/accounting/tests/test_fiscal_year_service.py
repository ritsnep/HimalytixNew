from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.test import TestCase
from django.utils import timezone

from accounting.models import AccountingPeriod, FiscalYear
from usermanagement.models import Organization
from accounting.services.fiscal_year_service import close_fiscal_year, reopen_fiscal_year


class FiscalYearServiceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.organization = Organization.objects.create(name="Org", code="ORG")
        self.user = User.objects.create_user(username="manager", password="pass123")
        self.user.organization = self.organization
        self.user.is_superuser = True
        self.user.save()

        start = timezone.datetime(2024, 4, 1, tzinfo=timezone.utc)
        end = timezone.datetime(2025, 3, 31, tzinfo=timezone.utc)
        self.fiscal_year = FiscalYear.objects.create(
            organization=self.organization,
            code="FY24",
            name="FY 2024",
            start_date=start.date(),
            end_date=end.date(),
            is_current=True,
            created_by=self.user,
        )
        AccountingPeriod.objects.create(
            fiscal_year=self.fiscal_year,
            period_number=1,
            name="Apr 2024",
            start_date=start.date(),
            end_date=(start + timezone.timedelta(days=29)).date(),
            status="open",
            created_by=self.user,
        )
        AccountingPeriod.objects.create(
            fiscal_year=self.fiscal_year,
            period_number=2,
            name="May 2024",
            start_date=(start + timezone.timedelta(days=30)).date(),
            end_date=(start + timezone.timedelta(days=60)).date(),
            status="open",
            created_by=self.user,
        )

    def test_close_fiscal_year_requires_closed_periods(self):
        with self.assertRaises(ValidationError):
            close_fiscal_year(self.fiscal_year, user=self.user, auto_close_open_periods=False)

        close_fiscal_year(self.fiscal_year, user=self.user, auto_close_open_periods=True)
        self.fiscal_year.refresh_from_db()
        self.assertEqual(self.fiscal_year.status, "closed")
        self.assertFalse(self.fiscal_year.is_current)
        self.assertEqual(self.fiscal_year.periods.filter(status="closed").count(), 2)

    def test_reopen_closed_fiscal_year(self):
        close_fiscal_year(self.fiscal_year, user=self.user, auto_close_open_periods=True)
        reopened = reopen_fiscal_year(self.fiscal_year, user=self.user)
        self.assertEqual(reopened.status, "open")
        self.assertTrue(reopened.is_current)

    def test_close_requires_permission(self):
        with self.assertRaises(PermissionDenied):
            close_fiscal_year(self.fiscal_year, user=None, auto_close_open_periods=True)
