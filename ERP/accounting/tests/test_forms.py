"""
Form tests for accounting forms.
"""
from django.test import TestCase
from accounting.forms import FiscalYearForm

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
