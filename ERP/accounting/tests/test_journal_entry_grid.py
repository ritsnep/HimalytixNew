from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase

from accounting.views.views_journal_grid import journal_entry_grid_save


class JournalEntryGridSaveTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(username="grid-user")
        self.organization = SimpleNamespace(name="Acme")

    def _make_request(self):
        request = self.factory.post("/accounting/journal-entry-grid/save", data={})
        request.user = self.user
        request.organization = self.organization
        return request

    def _build_form(self, debit, credit, account="1000"):
        form = MagicMock()
        form.is_valid.return_value = True
        form.cleaned_data = {
            "debit_amount": Decimal(debit),
            "credit_amount": Decimal(credit),
            "account": account,
            "description": "row",
            "department": None,
            "project": None,
            "cost_center": None,
            "txn_currency": "USD",
            "fx_rate": Decimal("1"),
            "memo": "",
        }
        return form

    @patch("accounting.views.views_journal_grid.JournalLine.objects.create")
    @patch("accounting.views.views_journal_grid.transaction.atomic")
    @patch("accounting.views.views_journal_grid.JournalGridLineFormSet")
    @patch("accounting.views.views_journal_grid.JournalForm")
    def test_save_rejects_unbalanced_totals(
        self,
        journal_form_cls,
        formset_cls,
        atomic_ctx,
        line_create,
    ):
        atomic_ctx.return_value.__enter__.return_value = None
        header_form = MagicMock()
        header_form.is_valid.return_value = True
        journal_stub = MagicMock()
        journal_stub.pk = None
        header_form.save.return_value = journal_stub
        journal_form_cls.return_value = header_form
        formset_cls.return_value = [
            self._build_form("100", "0"),
            self._build_form("0", "10"),
        ]

        request = self._make_request()

        response = journal_entry_grid_save(request)

        self.assertEqual(response.status_code, 422)
        self.assertIn(b"Debits and credits must balance", response.content)
        line_create.assert_not_called()

    @patch("accounting.views.views_journal_grid.JournalLine.objects.create")
    @patch("accounting.views.views_journal_grid.transaction.atomic")
    @patch("accounting.views.views_journal_grid.JournalGridLineFormSet")
    @patch("accounting.views.views_journal_grid.JournalForm")
    def test_save_creates_balanced_journal(
        self,
        journal_form_cls,
        formset_cls,
        atomic_ctx,
        line_create,
    ):
        atomic_ctx.return_value.__enter__.return_value = None
        header_form = MagicMock()
        header_form.is_valid.return_value = True
        journal_stub = MagicMock()
        journal_stub.pk = None
        header_form.save.return_value = journal_stub
        journal_form_cls.return_value = header_form
        formset_cls.return_value = [
            self._build_form("100", "0"),
            self._build_form("0", "100"),
        ]

        request = self._make_request()

        response = journal_entry_grid_save(request)

        self.assertEqual(response.status_code, 200)
        line_create.assert_called()
        self.assertEqual(line_create.call_count, 2)

    @patch("accounting.views.views_journal_grid.JournalLine.objects.create")
    @patch("accounting.views.views_journal_grid.transaction.atomic")
    @patch("accounting.views.views_journal_grid.JournalGridLineFormSet")
    @patch("accounting.views.views_journal_grid.JournalForm")
    def test_save_ignores_blank_rows_before_balancing(
        self,
        journal_form_cls,
        formset_cls,
        atomic_ctx,
        line_create,
    ):
        atomic_ctx.return_value.__enter__.return_value = None
        header_form = MagicMock()
        header_form.is_valid.return_value = True
        journal_stub = MagicMock()
        journal_stub.pk = None
        header_form.save.return_value = journal_stub
        journal_form_cls.return_value = header_form
        formset_cls.return_value = [
            self._build_form("0", "0", account=None),
            self._build_form("75", "0"),
            self._build_form("0", "75"),
        ]

        request = self._make_request()

        response = journal_entry_grid_save(request)

        self.assertEqual(response.status_code, 200)
        line_create.assert_called()
        self.assertEqual(line_create.call_count, 2)

    @patch("accounting.views.views_journal_grid.JournalLine.objects.create")
    @patch("accounting.views.views_journal_grid.transaction.atomic")
    @patch("accounting.views.views_journal_grid.JournalGridLineFormSet")
    @patch("accounting.views.views_journal_grid.JournalForm")
    def test_save_rejects_when_all_rows_are_blank(
        self,
        journal_form_cls,
        formset_cls,
        atomic_ctx,
        line_create,
    ):
        atomic_ctx.return_value.__enter__.return_value = None
        header_form = MagicMock()
        header_form.is_valid.return_value = True
        journal_stub = MagicMock()
        journal_stub.pk = None
        header_form.save.return_value = journal_stub
        journal_form_cls.return_value = header_form
        formset_cls.return_value = [
            self._build_form("0", "0", account=None),
        ]

        request = self._make_request()

        response = journal_entry_grid_save(request)

        self.assertEqual(response.status_code, 422)
        self.assertIn(b"No lines", response.content)
        line_create.assert_not_called()
