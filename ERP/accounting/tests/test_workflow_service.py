from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from accounting.models import ApprovalStep, ApprovalWorkflow
from accounting.services.workflow_service import WorkflowService
from accounting.tests import factories as f
from configuration.models import ConfigurationEntry
from configuration.services import ConfigurationService


class WorkflowServiceTests(TestCase):
    def setUp(self):
        self.organization = f.create_organization()
        self.manager = f.create_user(organization=self.organization, role="manager")
        self.cfo = f.create_user(organization=self.organization, role="cfo")
        self.analyst = f.create_user(organization=self.organization, role="analyst")
        for user in (self.manager, self.cfo, self.analyst):
            user.get_active_organization = lambda org=self.organization: org

        self.journal = f.create_journal(
            organization=self.organization,
            created_by=self.manager,
            total_debit=500,
            total_credit=500,
        )
        self.workflow = ApprovalWorkflow.objects.create(
            organization=self.organization,
            name="Journal Flow",
            area="journal",
        )
        ApprovalStep.objects.create(
            workflow=self.workflow,
            sequence=1,
            role="manager",
            min_amount=0,
        )
        ApprovalStep.objects.create(
            workflow=self.workflow,
            sequence=2,
            role="cfo",
            min_amount=1000,
        )

    def test_submit_with_policy_uses_configured_workflow(self):
        ConfigurationService.set_value(
            organization=self.organization,
            scope=ConfigurationEntry.SCOPE_FINANCE,
            key="approval_workflows",
            value={"journal": self.workflow.name},
        )
        task = WorkflowService(self.manager).submit_with_policy(
            self.journal,
            area="journal",
            initiator=self.manager,
        )
        self.assertEqual(task.workflow, self.workflow)
        self.assertEqual(task.status, "pending")

    def test_approve_enforces_roles_and_skips_thresholds(self):
        task = WorkflowService(self.manager).submit(self.journal, self.workflow, initiator=self.manager)

        with self.assertRaises(PermissionDenied):
            WorkflowService(self.analyst).approve(task, self.analyst, approved=True)

        WorkflowService(self.manager).approve(task, self.manager, approved=True)
        task.refresh_from_db()
        # Amount is below CFO threshold so workflow finishes after manager approval.
        self.assertEqual(task.status, "approved")

    def test_submit_with_policy_without_workflow_raises(self):
        with self.assertRaises(ValidationError):
            WorkflowService(self.manager).submit_with_policy(self.journal, area="payment", initiator=self.manager)
