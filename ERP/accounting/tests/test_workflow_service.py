from datetime import date
from decimal import Decimal

from django.test import TestCase

from accounting.models import (
    AccountType,
    ApprovalStep,
    ApprovalWorkflow,
    ChartOfAccount,
    Currency,
    FiscalYear,
    Journal,
    JournalType,
    Organization,
)
from accounting.services.workflow_service import WorkflowService
from accounting.tests import factories
from usermanagement.models import CustomUser


class WorkflowServiceTests(TestCase):
    def setUp(self):
        self.org = factories.create_organization(name='WF Org', code='WF')
        self.currency = factories.create_currency(code='USD', name='US Dollar', symbol='$')
        self.fiscal_year = factories.create_fiscal_year(
            organization=self.org,
            code='WF22',
            name='FY22',
            start_date=date(2022, 1, 1),
            end_date=date(2022, 12, 31),
            is_current=True,
        )
        self.period = factories.create_accounting_period(
            fiscal_year=self.fiscal_year,
            period_number=1,
            name='P1',
            start_date=date(2022, 1, 1),
            end_date=date(2022, 1, 31),
            is_current=True,
        )
        self.journal_type = factories.create_journal_type(
            organization=self.org,
            code='GEN',
            name='General',
        )
        acc_type = factories.create_account_type(code='EXP300', nature='expense', name='Expense')
        self.account = factories.create_chart_of_account(
            organization=self.org,
            account_type=acc_type,
            currency=self.currency,
            account_code='5002',
            account_name='Consulting Expense',
        )
        self.user = factories.create_user(username='wfuser', password='pass', organization=self.org)
        self.workflow = ApprovalWorkflow.objects.create(
            organization=self.org,
            name='Journal Approval',
            area='journal',
        )
        ApprovalStep.objects.bulk_create([
            ApprovalStep(workflow=self.workflow, sequence=1, role='approver', min_amount=0),
            ApprovalStep(workflow=self.workflow, sequence=2, role='manager', min_amount=0),
        ])
        self.service = WorkflowService(self.user)

    def create_journal(self):
        return factories.create_journal(
            organization=self.org,
            journal_type=self.journal_type,
            period=self.period,
            journal_date=date(2022, 1, 5),
            currency_code='USD',
            journal_number='GEN-001',
            created_by=self.user,
        )

    def test_submit_and_approve_journal(self):
        journal = self.create_journal()
        task = self.service.submit(journal, self.workflow, initiator=self.user)
        self.assertEqual(task.status, 'pending')
        task = self.service.approve(task, user=self.user, approved=True, notes='ok')
        self.assertEqual(task.status, 'pending')
        self.assertEqual(task.current_step, 2)
        task = self.service.approve(task, user=self.user, approved=True)
        self.assertEqual(task.status, 'approved')

    def test_reject_sets_status(self):
        journal = self.create_journal()
        task = self.service.submit(journal, self.workflow, initiator=self.user)
        self.service.approve(task, user=self.user, approved=False, notes='no')
        task.refresh_from_db()
        self.assertEqual(task.status, 'rejected')
