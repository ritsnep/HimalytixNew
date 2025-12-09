from datetime import date
from decimal import Decimal

from django.test import TestCase

from accounting.models import (
    AccountingPeriod,
    AccountType,
    ChartOfAccount,
    Currency,
    Customer,
    FiscalYear,
    JournalLine,
    JournalType,
    PaymentTerm,
    TaxCode,
    TaxType,
)
from accounting.services.sales_invoice_service import SalesInvoiceService
from usermanagement.models import CustomUser, Organization


class SalesInvoiceTaxTests(TestCase):
    def setUp(self) -> None:
        self.organization = Organization.objects.create(name="Tax Org", code="TAXORG", type="company")
        self.currency, _ = Currency.objects.get_or_create(
            currency_code="NPR",
            defaults={"currency_name": "Nepalese Rupee", "symbol": "Rs"},
        )

        self.asset_type = AccountType.objects.create(
            code="AST",
            name="Asset",
            nature="asset",
            classification="balance",
            display_order=1,
        )
        self.revenue_type = AccountType.objects.create(
            code="REV",
            name="Revenue",
            nature="income",
            classification="income",
            display_order=2,
        )
        self.liability_type = AccountType.objects.create(
            code="LIA",
            name="Liability",
            nature="liability",
            classification="balance",
            display_order=3,
        )

        today = date(2025, 1, 10)
        fiscal_year = FiscalYear.objects.create(
            organization=self.organization,
            code="FY25",
            name="Fiscal 2025",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            status="open",
            is_current=True,
        )
        AccountingPeriod.objects.create(
            organization=self.organization,
            fiscal_year=fiscal_year,
            name="Jan 2025",
            period_number=1,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            status="open",
            is_current=True,
        )

        self.ar_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=self.asset_type,
            account_code="1100",
            account_name="Accounts Receivable",
            currency=self.currency,
        )
        self.revenue_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=self.revenue_type,
            account_code="4000",
            account_name="Sales Revenue",
            currency=self.currency,
        )
        self.tax_account_primary = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=self.liability_type,
            account_code="2100",
            account_name="Output Tax",
            currency=self.currency,
        )
        self.tax_account_secondary = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=self.liability_type,
            account_code="2101",
            account_name="Local Tax",
            currency=self.currency,
        )

        self.payment_term = PaymentTerm.objects.create(
            organization=self.organization,
            code="NET15",
            name="Net 15",
            term_type="ar",
            net_due_days=15,
        )
        self.customer = Customer.objects.create(
            organization=self.organization,
            code="CUST1",
            display_name="Test Customer",
            accounts_receivable_account=self.ar_account,
            default_currency=self.currency,
            payment_term=self.payment_term,
        )
        self.user = CustomUser.objects.create_user(
            username="tax_user",
            password="pass",
            organization=self.organization,
            full_name="Tax User",
            role="superadmin",
            is_staff=True,
            is_superuser=True,
        )
        self.service = SalesInvoiceService(self.user)
        self.journal_type = JournalType.objects.create(
            organization=self.organization,
            code="SI",
            name="Sales",
        )
        tax_type = TaxType.objects.create(
            organization=self.organization,
            code="VAT",
            name="VAT",
        )
        self.tax_primary = TaxCode.objects.create(
            organization=self.organization,
            tax_type=tax_type,
            code="VAT13",
            name="VAT 13%",
            tax_rate=Decimal("13"),
            sales_account=self.tax_account_primary,
        )
        self.tax_secondary = TaxCode.objects.create(
            organization=self.organization,
            tax_type=tax_type,
            code="LOC5",
            name="Local Tax 5% (compound)",
            tax_rate=Decimal("5"),
            is_compound=True,
            sales_account=self.tax_account_secondary,
        )

    def test_multi_tax_breakdown_creates_journal_lines(self):
        base_amount = Decimal("100.00")
        vat_amount = Decimal("13.00")
        compound_base = base_amount + vat_amount
        local_tax_amount = (compound_base * Decimal("0.05")).quantize(Decimal("0.01"))
        total_tax = vat_amount + local_tax_amount

        invoice = self.service.create_invoice(
            organization=self.organization,
            customer=self.customer,
            invoice_date=date(2025, 1, 10),
            currency=self.currency,
            lines=[
                {
                    "description": "Taxed item",
                    "quantity": Decimal("1"),
                    "unit_price": base_amount,
                    "revenue_account": self.revenue_account,
                    "tax_amount": total_tax,
                    "tax_code": self.tax_primary,
                    "tax_breakdown": [
                        {"tax_code": self.tax_primary, "base_amount": base_amount, "tax_amount": vat_amount},
                        {"tax_code": self.tax_secondary, "base_amount": compound_base, "tax_amount": local_tax_amount},
                    ],
                }
            ],
        )
        invoice = self.service.validate_invoice(invoice)
        journal = self.service.post_invoice(invoice, self.journal_type)

        invoice.refresh_from_db()
        self.assertEqual(invoice.tax_total, total_tax)

        lines = JournalLine.objects.filter(journal=journal)
        self.assertEqual(lines.count(), 4)

        tax_lines = lines.filter(account__in=[self.tax_account_primary, self.tax_account_secondary])
        self.assertEqual(tax_lines.count(), 2)
        self.assertEqual(tax_lines.get(account=self.tax_account_primary).credit_amount, vat_amount)
        self.assertEqual(tax_lines.get(account=self.tax_account_secondary).credit_amount, local_tax_amount)

        ar_line = lines.get(account=self.ar_account)
        self.assertEqual(ar_line.debit_amount, base_amount + total_tax)
