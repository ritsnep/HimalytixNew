from django.test import TestCase
from django.db.models.signals import pre_save, post_save
from notification_center import signals as notify_signals

from accounting.forms.form_factory import VoucherFormFactory
from accounting.forms.journal_form import JournalForm
from accounting.forms.journal_line_form import JournalLineForm
from accounting.forms.currency_exchange_rate_form import CurrencyExchangeRateForm
from accounting.models import Currency, VoucherModeConfig
from usermanagement.models import Organization


class FormDefaultsTestCase(TestCase):
    def setUp(self):
        # Disconnect notification signals to prevent recursion during test DB setup
        try:
            pre_save.disconnect(receiver=notify_signals.notification_pre_save)
            post_save.disconnect(receiver=notify_signals.notification_post_save)
        except Exception:
            pass
        # Create currencies
        self.usd = Currency.objects.create(currency_code='USD', currency_name='US Dollar')
        self.npr = Currency.objects.create(currency_code='NPR', currency_name='Nepalese Rupee')
        # Create organization with NPR as base currency
        self.org = Organization.objects.create(code='ORG1', name='Test Org', base_currency_code=self.npr)

    def test_journal_form_currency_initial(self):
        form = VoucherFormFactory.get_journal_form(organization=self.org)
        self.assertEqual(form.initial.get('currency_code'), self.org.base_currency_code_id)

    def test_journal_line_form_txn_currency_initial(self):
        form = VoucherFormFactory.get_journal_line_form(organization=self.org)
        self.assertEqual(form.initial.get('txn_currency'), self.org.base_currency_code_id)

    def test_exchange_rate_form_from_currency_initial(self):
        form = CurrencyExchangeRateForm(organization=self.org)
        self.assertEqual(form.initial.get('from_currency'), self.org.base_currency_code_id)

    def tearDown(self):
        # Reconnect notification signals after tests
        try:
            pre_save.connect(notify_signals.notification_pre_save)
            post_save.connect(notify_signals.notification_post_save)
        except Exception:
            pass
