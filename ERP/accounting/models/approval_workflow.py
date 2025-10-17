"""
Approval Workflow Models - Phase 3 Task 1

Database models for managing journal entry approval workflows:
- ApprovalWorkflow: Define approval rules
- ApprovalStep: Approval chain steps
- ApprovalLog: Track all approvals
- ApprovalNotification: Notification queue
"""

from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class ApprovalWorkflow(models.Model):
    """
    Define approval workflow rules for journals.
    
    Attributes:
        name: Workflow name (e.g., "Standard Approval")
        code: Unique code for reference
        description: Workflow description
        organization: Organization this workflow belongs to
        journal_type: Journal type this workflow applies to
        amount_threshold: Minimum amount requiring approval
        approver_count: Number of approvers required
        parallel_approval: Approve in parallel vs sequential
        auto_post_after_approval: Auto-post journal when approved
        is_active: Whether workflow is enabled
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """
    
    APPROVAL_TYPE_SEQUENTIAL = 'sequential'
    APPROVAL_TYPE_PARALLEL = 'parallel'
    APPROVAL_TYPES = [
        (APPROVAL_TYPE_SEQUENTIAL, _('Sequential - One at a time')),
        (APPROVAL_TYPE_PARALLEL, _('Parallel - All simultaneously')),
    ]
    
    name = models.CharField(
        max_length=100,
        help_text=_('Name of the approval workflow')
    )
    code = models.CharField(
        max_length=50,
        unique=True,
        help_text=_('Unique code for reference')
    )
    description = models.TextField(
        blank=True,
        help_text=_('Description of workflow purpose')
    )
    organization = models.ForeignKey(
        'usermanagement.Organization',
        on_delete=models.CASCADE,
        related_name='approval_workflows'
    )
    journal_type = models.ForeignKey(
        'accounting.JournalType',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approval_workflows',
        help_text=_('Leave blank to apply to all types')
    )
    amount_threshold = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text=_('Minimum journal amount requiring approval')
    )
    approver_count = models.IntegerField(
        default=1,
        help_text=_('Number of approvers required')
    )
    approval_type = models.CharField(
        max_length=20,
        choices=APPROVAL_TYPES,
        default=APPROVAL_TYPE_SEQUENTIAL
    )
    auto_post_after_approval = models.BooleanField(
        default=False,
        help_text=_('Auto-post journal when all approvals complete')
    )
    is_active = models.BooleanField(
        default=True,
        help_text=_('Whether this workflow is active')
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_workflows'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'approval_workflows'
        verbose_name = _('Approval Workflow')
        verbose_name_plural = _('Approval Workflows')
        indexes = [
            models.Index(fields=['organization', 'is_active']),
            models.Index(fields=['code']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    def get_steps(self):
        """Get all approval steps in order."""
        return self.steps.filter(is_active=True).order_by('step_order')
    
    def get_next_approvers(self, journal):
        """Get list of next approvers for a journal."""
        approval_log = ApprovalLog.objects.filter(
            journal=journal,
            workflow=self,
            status='pending'
        ).first()
        
        if not approval_log:
            return []
        
        if self.approval_type == self.APPROVAL_TYPE_SEQUENTIAL:
            pending_steps = approval_log.get_pending_steps()
            if pending_steps:
                return list(pending_steps[0].approvers.all())
        else:
            # Parallel: all pending steps
            pending_steps = approval_log.get_pending_steps()
            approvers = set()
            for step in pending_steps:
                approvers.update(step.approvers.all())
            return list(approvers)
        
        return []


class ApprovalStep(models.Model):
    """
    Individual step in an approval workflow.
    
    Attributes:
        workflow: Parent workflow
        step_order: Order in workflow (1-based)
        name: Step name (e.g., "Manager Review")
        description: Step description
        approvers: Users who can approve at this step
        required_count: How many approvers must approve
        timeout_days: Days before approval times out
        conditions: JSON conditions for step execution
    """
    
    workflow = models.ForeignKey(
        ApprovalWorkflow,
        on_delete=models.CASCADE,
        related_name='steps'
    )
    step_order = models.IntegerField(
        help_text=_('Order of this step in workflow (1-based)')
    )
    name = models.CharField(
        max_length=100,
        help_text=_('Name of this approval step')
    )
    description = models.TextField(
        blank=True,
        help_text=_('Description of what this step validates')
    )
    approvers = models.ManyToManyField(
        User,
        related_name='approval_steps',
        help_text=_('Users who can approve at this step')
    )
    required_count = models.IntegerField(
        default=1,
        help_text=_('How many approvers must approve')
    )
    timeout_days = models.IntegerField(
        default=5,
        help_text=_('Days before approval auto-escalates')
    )
    conditions = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('JSON conditions for step execution (e.g., amount thresholds)')
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'approval_steps'
        verbose_name = _('Approval Step')
        verbose_name_plural = _('Approval Steps')
        unique_together = [['workflow', 'step_order']]
        indexes = [
            models.Index(fields=['workflow', 'step_order']),
        ]
    
    def __str__(self):
        return f"{self.workflow.name} - Step {self.step_order}: {self.name}"
    
    def get_timeout_date(self):
        """Calculate timeout date for this step."""
        return datetime.now() + timedelta(days=self.timeout_days)
    
    def check_condition(self, journal) -> bool:
        """Check if conditions are met for this step."""
        if not self.conditions:
            return True
        
        # Check amount threshold
        if 'min_amount' in self.conditions:
            if journal.total_debit < self.conditions['min_amount']:
                return False
        
        if 'max_amount' in self.conditions:
            if journal.total_debit > self.conditions['max_amount']:
                return False
        
        # Add more condition checks as needed
        
        return True


class ApprovalLog(models.Model):
    """
    Track approval history for a journal.
    
    Attributes:
        journal: The journal being approved
        workflow: Workflow being used
        status: Current approval status
        submitted_by: User who submitted for approval
        submitted_at: When submitted
        approval_steps: JSON tracking step status
        current_step: Current step number
        escalation_count: How many times escalated
    """
    
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_ESCALATED = 'escalated'
    STATUSES = [
        (STATUS_PENDING, _('Pending')),
        (STATUS_APPROVED, _('Approved')),
        (STATUS_REJECTED, _('Rejected')),
        (STATUS_ESCALATED, _('Escalated')),
    ]
    
    journal = models.OneToOneField(
        'accounting.Journal',
        on_delete=models.CASCADE,
        related_name='approval_log'
    )
    workflow = models.ForeignKey(
        ApprovalWorkflow,
        on_delete=models.SET_NULL,
        null=True,
        related_name='approval_logs'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUSES,
        default=STATUS_PENDING
    )
    submitted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='submitted_for_approval'
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    current_step = models.IntegerField(default=1)
    step_status = models.JSONField(
        default=dict,
        help_text=_('Track status of each step')
    )
    escalation_count = models.IntegerField(default=0)
    rejection_reason = models.TextField(
        blank=True,
        help_text=_('Reason for rejection if rejected')
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('When approval process completed')
    )
    
    class Meta:
        db_table = 'approval_logs'
        verbose_name = _('Approval Log')
        verbose_name_plural = _('Approval Logs')
        indexes = [
            models.Index(fields=['journal', 'status']),
            models.Index(fields=['workflow', 'status']),
        ]
    
    def __str__(self):
        return f"Approval: {self.journal.reference_no} - {self.get_status_display()}"
    
    def get_pending_steps(self):
        """Get all pending steps."""
        workflow = self.workflow
        pending_steps = []
        
        for step in workflow.get_steps():
            step_key = f'step_{step.step_order}'
            if self.step_status.get(step_key, {}).get('status') == 'pending':
                pending_steps.append(step)
        
        return pending_steps
    
    def get_current_step_approvers(self):
        """Get approvers for current step."""
        step = self.workflow.steps.filter(step_order=self.current_step).first()
        if step:
            return list(step.approvers.all())
        return []
    
    def is_complete(self) -> bool:
        """Check if all steps are approved."""
        for step in self.workflow.get_steps():
            step_key = f'step_{step.step_order}'
            if self.step_status.get(step_key, {}).get('status') != 'approved':
                return False
        return True
    
    def mark_step_approved(self, step_number: int):
        """Mark a step as approved."""
        step_key = f'step_{step_number}'
        if step_key not in self.step_status:
            self.step_status[step_key] = {}
        
        self.step_status[step_key]['status'] = 'approved'
        self.step_status[step_key]['approved_at'] = datetime.now().isoformat()
        
        if self.is_complete():
            self.status = self.STATUS_APPROVED
            self.completed_at = datetime.now()
        
        self.save()
        logger.info(f"Step {step_number} approved for journal {self.journal.id}")


class ApprovalDecision(models.Model):
    """
    Individual approval decision for a journal.
    
    Attributes:
        approval_log: Parent approval log
        step: Approval step
        approver: User who made decision
        decision: Approve or Reject
        comments: Approval comments
        decided_at: When decided
    """
    
    DECISION_APPROVE = 'approve'
    DECISION_REJECT = 'reject'
    DECISIONS = [
        (DECISION_APPROVE, _('Approve')),
        (DECISION_REJECT, _('Reject')),
    ]
    
    approval_log = models.ForeignKey(
        ApprovalLog,
        on_delete=models.CASCADE,
        related_name='decisions'
    )
    step = models.ForeignKey(
        ApprovalStep,
        on_delete=models.SET_NULL,
        null=True,
        related_name='decisions'
    )
    approver = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='approval_decisions'
    )
    decision = models.CharField(
        max_length=20,
        choices=DECISIONS
    )
    comments = models.TextField(
        blank=True,
        help_text=_('Approval comments or rejection reason')
    )
    decided_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'approval_decisions'
        verbose_name = _('Approval Decision')
        verbose_name_plural = _('Approval Decisions')
        indexes = [
            models.Index(fields=['approval_log', 'approver']),
            models.Index(fields=['decision']),
        ]
    
    def __str__(self):
        return f"{self.approver.username}: {self.get_decision_display()} @ {self.decided_at}"


class ApprovalNotification(models.Model):
    """
    Notification queue for approval events.
    
    Attributes:
        approval_log: Related approval log
        recipient: User to notify
        notification_type: Type of notification
        sent: Whether notification was sent
        sent_at: When sent
    """
    
    TYPE_SUBMITTED = 'submitted'
    TYPE_NEEDS_APPROVAL = 'needs_approval'
    TYPE_APPROVED = 'approved'
    TYPE_REJECTED = 'rejected'
    TYPE_ESCALATED = 'escalated'
    TYPES = [
        (TYPE_SUBMITTED, _('Journal Submitted')),
        (TYPE_NEEDS_APPROVAL, _('Needs Approval')),
        (TYPE_APPROVED, _('Journal Approved')),
        (TYPE_REJECTED, _('Journal Rejected')),
        (TYPE_ESCALATED, _('Approval Escalated')),
    ]
    
    approval_log = models.ForeignKey(
        ApprovalLog,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='approval_notifications'
    )
    notification_type = models.CharField(
        max_length=20,
        choices=TYPES
    )
    sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'approval_notifications'
        verbose_name = _('Approval Notification')
        verbose_name_plural = _('Approval Notifications')
        indexes = [
            models.Index(fields=['recipient', 'sent']),
            models.Index(fields=['notification_type']),
        ]
    
    def __str__(self):
        return f"{self.get_notification_type_display()} for {self.recipient.username}"
