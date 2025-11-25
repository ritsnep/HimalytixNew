from datetime import date
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounting.models import Customer, PurchaseInvoice, SalesInvoice, Vendor
from accounting.tests import factories


class ComplianceAPITests(APITestCase):
    def setUp(self):
        self.organization = factories.create_organization(name='Compliance Org', code='COMP')
        self.currency = factories.create_currency()
        self.expense_type = factories.create_account_type(nature='expense')
        self.revenue_type = factories.create_account_type(nature='income')
        self.asset_type = factories.create_account_type(nature='asset')
        self.liability_type = factories.create_account_type(nature='liability')
        self.expense_account = factories.create_chart_of_account(
            organization=self.organization,
            account_type=self.expense_type,
            currency=self.currency,
        )
        self.revenue_account = factories.create_chart_of_account(
            organization=self.organization,
            account_type=self.revenue_type,
            currency=self.currency,
        )
        self.ap_account = factories.create_chart_of_account(
            organization=self.organization,
            account_type=self.liability_type,
            currency=self.currency,
        )
        self.ar_account = factories.create_chart_of_account(
            organization=self.organization,
            account_type=self.asset_type,
            currency=self.currency,
        )
        authority = factories.create_tax_authority(organization=self.organization)
        tax_type = factories.create_tax_type(organization=self.organization, authority=authority)
        self.tax_code = factories.create_tax_code(
            organization=self.organization,
            tax_type=tax_type,
            authority=authority,
            rate=Decimal('0.13'),
            tax_rate=Decimal('0.13'),
        )
        self.user = factories.create_user(organization=self.organization)
        self.client.force_authenticate(user=self.user)
        self.customer = Customer.objects.create(
            organization=self.organization,
            code='CUST1',
            display_name='Customer One',
            accounts_receivable_account=self.ar_account,
            revenue_account=self.revenue_account,
        )
        self.vendor = Vendor.objects.create(
            organization=self.organization,
            code='VEND1',
            display_name='Vendor One',
            accounts_payable_account=self.ap_account,
            expense_account=self.expense_account,
        )
        self.period_start = date(2025, 1, 1)
        self._seed_invoices()

    def _seed_invoices(self):
        sales_invoice = SalesInvoice.objects.create(
            organization=self.organization,
            customer=self.customer,
            customer_display_name=self.customer.display_name,
            invoice_number='SI-100',
            invoice_date=self.period_start,
            due_date=self.period_start,
            currency=self.currency,
            exchange_rate=Decimal('1'),
            subtotal=Decimal('100'),
            tax_total=Decimal('13'),
            total=Decimal('113'),
            base_currency_total=Decimal('113'),
            status='posted',
        )
        sales_invoice.lines.create(
            line_number=1,
            description='Sales',
            quantity=1,
            unit_price=Decimal('100'),
            revenue_account=self.revenue_account,
            tax_code=self.tax_code,
            tax_amount=Decimal('13'),
        )
        purchase_invoice = PurchaseInvoice.objects.create(
            organization=self.organization,
            vendor=self.vendor,
            vendor_display_name=self.vendor.display_name,
            invoice_number='PI-100',
            invoice_date=self.period_start,
            due_date=self.period_start,
            currency=self.currency,
            exchange_rate=Decimal('1'),
            subtotal=Decimal('40'),
            tax_total=Decimal('5.20'),
            total=Decimal('45.20'),
            base_currency_total=Decimal('45.20'),
            status='posted',
        )
        purchase_invoice.lines.create(
            line_number=1,
            description='Supplies',
            quantity=1,
            unit_cost=Decimal('40'),
            account=self.expense_account,
            tax_code=self.tax_code,
            tax_amount=Decimal('5.20'),
        )

    def test_vat_summary_endpoint(self):
        url = reverse('accounting:compliance_vat_summary')
        response = self.client.get(url, {'period': '2025-01'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        total_output = Decimal(str(response.data['total_output_tax']))
        total_input = Decimal(str(response.data['total_input_tax']))
        self.assertEqual(total_output, Decimal('13'))
        self.assertEqual(total_input.quantize(Decimal('0.01')), Decimal('5.20'))
        self.assertEqual(len(response.data['lines']), 1)

    def test_nfrs_schedule_endpoint(self):
        url = reverse('accounting:compliance_nfrs_schedule')
        response = self.client.get(url, {'period': '2025-01'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        totals = response.data['totals']
        liability_balance = Decimal(str(totals['liability_balance']))
        self.assertEqual(liability_balance.quantize(Decimal('0.01')), Decimal('7.80'))
        self.assertEqual(response.data['assets'], [])
        self.assertEqual(len(response.data['liabilities']), 1)
