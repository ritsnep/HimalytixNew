from decimal import Decimal
from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from accounting.forms import ExpenseEntryForm
from accounting.models import ExpenseCategory, ExpenseEntry
from accounting.services import ExpenseEntryService
from accounting.tests.factories import (
    create_account_type,
    create_accounting_period,
    create_chart_of_account,
    create_fiscal_year,
    create_journal_type,
    create_organization,
    create_user,
)


def _ensure_current_period(organization):
    today = timezone.now().date()
    fiscal_year = create_fiscal_year(
        organization=organization,
        start_date=date(today.year, 1, 1),
        end_date=date(today.year, 12, 31),
    )
    create_accounting_period(
        fiscal_year=fiscal_year,
        start_date=fiscal_year.start_date,
        end_date=fiscal_year.end_date,
    )


class ExpenseEntryServiceTests(TestCase):
    def setUp(self):
        self.organization = create_organization()
        _ensure_current_period(self.organization)
        self.user = create_user(organization=self.organization)
        self.user.is_superuser = True
        self.user.save()
        expense_type = create_account_type(nature='expense', code='ATEXP-01')
        asset_type = create_account_type(nature='asset', code='ATAST-01')
        self.expense_account = create_chart_of_account(
            organization=self.organization,
            account_type=expense_type,
            account_code='5100',
            account_name='Default Expense',
        )
        self.payment_account = create_chart_of_account(
            organization=self.organization,
            account_type=asset_type,
            account_code='1100',
            account_name='Default Cash',
            is_bank_account=True,
        )
        self.category = ExpenseCategory.objects.create(
            organization=self.organization,
            code='GENEXP',
            name='General Expense',
            expense_account=self.expense_account,
            default_payment_account=self.payment_account,
        )
        self.journal_type = create_journal_type(organization=self.organization, code='EXPENSE')
        self.service = ExpenseEntryService(self.user, self.organization)

    def test_creates_balanced_journal_and_entry(self):
        entry = self.service.create_expense_entry(
            category=self.category,
            amount=Decimal('123.45'),
            payment_account=self.payment_account,
            paid_via=ExpenseEntry.PAID_VIA_BANK,
            description='Office supplies',
            reference='PO-1001',
            gst_applicable=True,
            gst_amount=Decimal('5.00'),
            journal_type=self.journal_type,
        )

        self.assertEqual(ExpenseEntry.objects.count(), 1)
        self.assertEqual(entry.amount, Decimal('123.45'))
        self.assertEqual(entry.gst_amount, Decimal('5.00'))
        journal = entry.journal
        self.assertEqual(journal.lines.count(), 2)
        self.assertEqual(journal.total_debit, Decimal('123.45'))
        self.assertEqual(journal.total_credit, Decimal('123.45'))
        debit_line = journal.lines.get(debit_amount__gt=0)
        credit_line = journal.lines.get(credit_amount__gt=0)
        self.assertEqual(debit_line.account, self.expense_account)
        self.assertEqual(credit_line.account, self.payment_account)
        self.assertEqual(credit_line.description, 'Paid via Bank')


class ExpenseEntryFormTests(TestCase):
    def setUp(self):
        self.organization = create_organization()
        _ensure_current_period(self.organization)
        expense_type = create_account_type(nature='expense', code='ATEXP-02')
        asset_type = create_account_type(nature='asset', code='ATAST-02')
        self.expense_account = create_chart_of_account(
            organization=self.organization,
            account_type=expense_type,
            account_code='5200',
            account_name='Expense Default',
        )
        self.payment_account = create_chart_of_account(
            organization=self.organization,
            account_type=asset_type,
            account_code='1200',
            account_name='Cash Default',
        )
        self.category = ExpenseCategory.objects.create(
            organization=self.organization,
            code='TRAVEL',
            name='Travel',
            expense_account=self.expense_account,
            default_payment_account=self.payment_account,
        )

    def _form_data(self, **overrides):
        data = {
            'category': self.category.pk,
            'entry_date': date.today().isoformat(),
            'amount': '200.00',
            'payment_account': self.payment_account.pk,
            'paid_via': ExpenseEntry.PAID_VIA_CASH,
            'gst_applicable': True,
            'gst_amount': '20.00',
        }
        data.update(overrides)
        return data

    def test_form_rejects_gst_greater_than_amount(self):
        form = ExpenseEntryForm(data=self._form_data(gst_amount='250.00'), organization=self.organization)
        self.assertFalse(form.is_valid())
        self.assertIn('GST amount cannot exceed the total amount.', form.non_field_errors())

    def test_form_requires_payment_account(self):
        form = ExpenseEntryForm(data=self._form_data(payment_account=''), organization=self.organization)
        self.assertFalse(form.is_valid())
        self.assertIn('A payment account is required to credit the ledger.', form.non_field_errors())

    def test_form_accepts_valid_data(self):
        form = ExpenseEntryForm(data=self._form_data(), organization=self.organization)
        self.assertTrue(form.is_valid())
