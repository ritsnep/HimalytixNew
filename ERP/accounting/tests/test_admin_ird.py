from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase
from django.utils import timezone

from accounting import admin as accounting_admin
from accounting.models import Customer, IRDSubmissionTask, SalesInvoice
from accounting.tests import factories


class _AdminSite(AdminSite):
    pass


class _AdminActionTestCase(TestCase):
    def _attach_messages(self, request):
        """Attach session + fallback message storage for admin actions."""
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()
        request._messages = FallbackStorage(request)
        return request


class SalesInvoiceAdminActionTests(_AdminActionTestCase):
    def setUp(self):
        self.site = _AdminSite()
        self.admin = accounting_admin.SalesInvoiceAdmin(SalesInvoice, self.site)
        self.factory = RequestFactory()
        self.organization = factories.create_organization()
        self.currency = factories.create_currency()
        self.receivable_type = factories.create_account_type(nature='asset')
        self.receivable_account = factories.create_chart_of_account(
            organization=self.organization,
            account_type=self.receivable_type,
            currency=self.currency,
        )
        self.customer = Customer.objects.create(
            organization=self.organization,
            code='C001',
            display_name='Customer One',
            accounts_receivable_account=self.receivable_account,
        )
        self.invoice = SalesInvoice.objects.create(
            organization=self.organization,
            customer=self.customer,
            customer_display_name=self.customer.display_name,
            invoice_number='INV-1',
            invoice_date=date.today(),
            due_date=date.today(),
            currency=self.currency,
            subtotal=Decimal('0'),
            tax_total=Decimal('0'),
            total=Decimal('0'),
            base_currency_total=Decimal('0'),
        )
        self.user = factories.create_user(organization=self.organization)
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save()

    def _build_request(self):
        request = self.factory.post('/admin/accounting/salesinvoice/')
        request.user = self.user
        return self._attach_messages(request)

    def test_queue_action_invokes_service(self):
        request = self._build_request()
        queryset = SalesInvoice.objects.filter(pk=self.invoice.pk)
        with mock.patch('accounting.admin.IRDSubmissionService') as service_cls:
            service_instance = service_cls.return_value
            self.admin.action_queue_ird_submission(request, queryset)
        service_cls.assert_called_once_with(self.user)
        service_instance.enqueue_invoice.assert_called_once_with(self.invoice)

    def test_reset_action_clears_metadata(self):
        self.invoice.ird_signature = 'sig'
        self.invoice.ird_ack_id = 'ACK-1'
        self.invoice.ird_status = 'failed'
        self.invoice.ird_last_response = {'detail': 'error'}
        self.invoice.ird_last_submitted_at = timezone.now()
        self.invoice.save(update_fields=[
            'ird_signature',
            'ird_ack_id',
            'ird_status',
            'ird_last_response',
            'ird_last_submitted_at',
        ])
        request = self._build_request()
        queryset = SalesInvoice.objects.filter(pk=self.invoice.pk)
        self.admin.action_reset_ird_metadata(request, queryset)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.ird_signature, '')
        self.assertEqual(self.invoice.ird_ack_id, '')
        self.assertEqual(self.invoice.ird_status, '')
        self.assertEqual(self.invoice.ird_last_response, {})
        self.assertIsNone(self.invoice.ird_last_submitted_at)


class IRDSubmissionTaskAdminActionTests(_AdminActionTestCase):
    def setUp(self):
        self.site = _AdminSite()
        self.admin = accounting_admin.IRDSubmissionTaskAdmin(IRDSubmissionTask, self.site)
        self.factory = RequestFactory()
        self.organization = factories.create_organization()
        self.currency = factories.create_currency()
        receivable_type = factories.create_account_type(nature='asset')
        receivable_account = factories.create_chart_of_account(
            organization=self.organization,
            account_type=receivable_type,
            currency=self.currency,
        )
        customer = Customer.objects.create(
            organization=self.organization,
            code='C002',
            display_name='Customer Two',
            accounts_receivable_account=receivable_account,
        )
        self.invoice = SalesInvoice.objects.create(
            organization=self.organization,
            customer=customer,
            customer_display_name=customer.display_name,
            invoice_number='INV-2',
            invoice_date=date.today(),
            due_date=date.today(),
            currency=self.currency,
            subtotal=Decimal('0'),
            tax_total=Decimal('0'),
            total=Decimal('0'),
            base_currency_total=Decimal('0'),
        )
        self.task = IRDSubmissionTask.objects.create(
            organization=self.organization,
            invoice=self.invoice,
            status=IRDSubmissionTask.STATUS_FAILED,
            priority=IRDSubmissionTask.PRIORITY_NORMAL,
        )
        self.user = factories.create_user(organization=self.organization)
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save()

    def test_retry_action_marks_pending_and_requeues(self):
        request = self.factory.post('/admin/accounting/irdsubmissiontask/')
        request.user = self.user
        self._attach_messages(request)
        queryset = IRDSubmissionTask.objects.filter(pk=self.task.pk)
        with mock.patch('accounting.admin.process_ird_submission') as process_task:
            self.admin.action_retry_submissions(request, queryset)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, IRDSubmissionTask.STATUS_PENDING)
        self.assertIsNotNone(self.task.next_attempt_at)
        process_task.delay.assert_called_once_with(self.task.pk)
