from datetime import date

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from accounting.forms import JournalForm, JournalLineForm
from accounting.models import (
    AccountingPeriod,
    AccountType,
    ChartOfAccount,
    Currency,
    FiscalYear,
    Journal,
    JournalLine,
    JournalType,
    UDFDefinition,
    UDFValue,
)
from accounting.utils.udf import filterable_udfs, pivot_udfs
from usermanagement.models import Organization


class UDFFormIntegrationTests(TestCase):
    maxDiff = None

    def setUp(self):
        self.organization = Organization.objects.create(name="Acme", code="ACM", type="company")
        self.currency = Currency.objects.create(currency_code="USD", currency_name="US Dollar", symbol="$")
        self.fiscal_year = FiscalYear.objects.create(
            organization=self.organization,
            code="FY25",
            name="FY 2025",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_current=True,
        )
        self.period = AccountingPeriod.objects.create(
            fiscal_year=self.fiscal_year,
            period_number=1,
            name="Jan 2025",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            status="open",
        )
        self.journal_type = JournalType.objects.create(
            organization=self.organization,
            code="GJ",
            name="General Journal",
        )
        self.account_type = AccountType.objects.create(
            code="EXP",
            name="Expense",
            nature="expense",
            classification="expense",
            display_order=1,
        )
        self.account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=self.account_type,
            account_code="5000",
            account_name="Expense",
        )
        self.journal = Journal.objects.create(
            organization=self.organization,
            journal_number="GJ-0001",
            journal_type=self.journal_type,
            period=self.period,
            journal_date=date(2025, 1, 15),
            currency_code="USD",
            exchange_rate=1,
            status="draft",
        )

    def _create_udf_definition(self, model, **overrides):
        defaults = {
            "organization": self.organization,
            "content_type": ContentType.objects.get_for_model(model),
            "field_name": overrides.pop("field_name", "custom_code"),
            "display_name": overrides.pop("display_name", "Custom Code"),
            "field_type": overrides.pop("field_type", "text"),
            "is_required": overrides.pop("is_required", False),
            "is_filterable": overrides.pop("is_filterable", False),
            "is_pivot_dim": overrides.pop("is_pivot_dim", False),
        }
        defaults.update(overrides)
        return UDFDefinition.objects.create(**defaults)

    def test_journal_form_renders_and_persists_udfs(self):
        definition = self._create_udf_definition(Journal, field_name="invoice_ref", display_name="Invoice")

        form_data = {
            "journal_type": str(self.journal_type.pk),
            "period": str(self.period.pk),
            "journal_date": "2025-01-15",
            "reference": "REF-1",
            "description": "Doc",
            "currency_code": "USD",
            "exchange_rate": "1",
            "status": "draft",
            "udf_invoice_ref": "INV-777",
        }
        form = JournalForm(data=form_data, organization=self.organization)
        self.assertIn("udf_invoice_ref", form.fields)
        self.assertTrue(form.is_valid(), form.errors)

        journal = form.save()
        stored = UDFValue.objects.get(udf_definition=definition, object_id=journal.pk)
        self.assertEqual(stored.value, "INV-777")
        self.assertEqual(journal.header_udf_data.get("udf_invoice_ref"), "INV-777")

    def test_journal_line_form_handles_udfs_and_json_payload(self):
        definition = self._create_udf_definition(JournalLine, field_name="line_reason", display_name="Reason")

        form_data = {
            "account": str(self.account.pk),
            "description": "Line",
            "debit_amount": "100",
            "credit_amount": "0",
            "txn_currency": self.currency.pk,
            "fx_rate": "1",
            "department": "",
            "project": "",
            "cost_center": "",
            "tax_code": "",
            "tax_rate": "",
            "tax_amount": "",
            "memo": "",
            "udf_data": "{}",
            "save_as_default": False,
            "udf_line_reason": "Accrual",
        }
        form = JournalLineForm(data=form_data, organization=self.organization, journal=self.journal)
        self.assertIn("udf_line_reason", form.fields)
        self.assertTrue(form.is_valid(), form.errors)

        form.instance.journal = self.journal
        line = form.save()
        stored = UDFValue.objects.get(udf_definition=definition, object_id=line.pk)
        self.assertEqual(stored.value, "Accrual")
        self.assertEqual(line.udf_data.get("udf_line_reason"), "Accrual")

    def test_udf_flag_helpers_filter_results(self):
        filter_def = self._create_udf_definition(Journal, field_name="filterable", is_filterable=True)
        pivot_def = self._create_udf_definition(JournalLine, field_name="pivot_only", is_pivot_dim=True)
        self._create_udf_definition(Journal, field_name="plain")

        filters = filterable_udfs(Journal, self.organization)
        pivots = pivot_udfs(JournalLine, self.organization)

        self.assertEqual([udf.field_name for udf in filters], [filter_def.field_name])
        self.assertEqual([udf.field_name for udf in pivots], [pivot_def.field_name])
