"""
Form tests for accounting forms.
"""
from django.test import TestCase, override_settings

from accounting.forms import ChartOfAccountForm, FiscalYearForm
from accounting.models import AccountType, ChartOfAccount
from usermanagement.models import Organization


class FiscalYearFormTest(TestCase):
    def test_valid_form(self):
        form = FiscalYearForm(data={
            'code': 'FY24',
            'name': '2024',
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'status': 'open',
            'is_current': True,
            'is_default': False
        })
        self.assertTrue(form.is_valid())


@override_settings(COA_MAX_DEPTH=3)
class ChartOfAccountFormDepthTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Acme Corp",
            code="ACME",
            type="company",
        )
        self.account_type = AccountType.objects.create(
            code="AST",
            name="Asset",
            nature="asset",
            classification="current",
            display_order=1,
        )
        self.root = self._create_account("1000", "Root")
        self.child = self._create_account("1000.01", "Child", parent=self.root)
        self.grandchild = self._create_account("1000.01.01", "Grandchild", parent=self.child)

    def _create_account(self, code, name, parent=None):
        return ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=self.account_type,
            parent_account=parent,
            account_code=code,
            account_name=name,
        )

    def _base_form_data(self, **overrides):
        data = {
            "account_name": "New Account",
            "account_type": str(self.account_type.pk),
            "parent_account": "",
            "opening_balance": "0.00",
            "current_balance": "0.00",
            "reconciled_balance": "0.00",
            "is_active": True,
            "is_bank_account": False,
            "is_control_account": False,
            "allow_manual_journal": True,
            "use_custom_code": False,
            "custom_code": "",
        }
        data.update(overrides)
        return data

    def test_form_blocks_accounts_beyond_depth_limit(self):
        form = ChartOfAccountForm(
            data=self._base_form_data(parent_account=str(self.grandchild.pk)),
            organization=self.organization,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("Account tree is too deep", form.errors["parent_account"][0])

    def test_form_accepts_account_within_depth_limit(self):
        form = ChartOfAccountForm(
            data=self._base_form_data(parent_account=str(self.child.pk)),
            organization=self.organization,
        )
        self.assertTrue(form.is_valid())
