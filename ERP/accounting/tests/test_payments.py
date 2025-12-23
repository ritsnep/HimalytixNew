from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
import json

from accounting.models import APPayment, APPaymentLine, Vendor, PurchaseInvoice, Journal, JournalType
from usermanagement.models import Organization, CustomUser
from accounting.services.app_payment_service import APPaymentService, PaymentAllocation


class PaymentPersistenceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="TestOrg", code="TST")
        self.user = CustomUser.objects.create_user(username='tester', password='pass')
        self.user.organizations.add(self.org)
        self.vendor = Vendor.objects.create(organization=self.org, display_name='Vend Inc')
        # Create an invoice to allocate against
        self.invoice = PurchaseInvoice.objects.create(
            organization=self.org,
            vendor=self.vendor,
            invoice_number='INV-1',
            invoice_date=timezone.now().date(),
            total_amount=Decimal('100.00')
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_app_payment_service_create_with_allocations(self):
        svc = APPaymentService(self.user)
        alloc = [PaymentAllocation(invoice=self.invoice, amount=Decimal('50.00'), discount=Decimal('0'))]
        payment = svc.create_payment(
            organization=self.org,
            vendor=self.vendor,
            payment_number='PY-1',
            payment_date=timezone.now().date(),
            bank_account=None,
            currency=None,
            exchange_rate=Decimal('1'),
            allocations=alloc,
            payment_method='bank_transfer'
        )
        self.assertIsInstance(payment, APPayment)
        self.assertEqual(payment.amount, Decimal('50.00'))
        lines = APPaymentLine.objects.filter(payment=payment)
        self.assertEqual(lines.count(), 1)
        line = lines.first()
        self.assertEqual(line.applied_amount, Decimal('50.00'))

    def test_voucher_edit_includes_payment_formset(self):
        # Create a journal and attach a payment
        jt = JournalType.objects.create(organization=self.org, code='PUR', name='Purchase')
        journal = Journal.objects.create(
            organization=self.org,
            journal_type=jt,
            journal_date=timezone.now().date(),
            description='Test Journal',
            status='draft',
            created_by=self.user,
            updated_by=self.user,
        )
        payment = APPayment.objects.create(
            organization=self.org,
            vendor=self.vendor,
            payment_number='PY-EDIT',
            payment_date=timezone.now().date(),
            payment_method='bank_transfer',
            amount=Decimal('10.00'),
            status='draft',
            journal=journal,
            created_by=self.user,
            updated_by=self.user,
        )

        # Access edit view
        url = reverse('accounting:voucher_edit', kwargs={'pk': journal.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        # Ensure payment_formset is present in context
        self.assertIn('payment_formset', resp.context)
        pfs = resp.context['payment_formset']
        # The formset should contain at least one form representing the saved payment
        found = any(getattr(f, 'instance', None) and f.instance.pk == payment.pk for f in pfs.forms)
        self.assertTrue(found)
