"""
Approval Workflow Views - Phase 3 Task 1

Views for managing journal approvals:
- ApprovalQueueView: List pending approvals
- VoucherApproveView: Approve a journal
- VoucherRejectView: Reject a journal
- ApprovalHistoryView: View approval history
- ApprovalDashboardView: Dashboard with statistics
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.db import transaction
from django.utils.translation import gettext as _
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.contrib import messages
import logging
from datetime import datetime

from accounting.models import Journal, JournalType
try:
    from accounting.models.approval_workflow import (
        ApprovalWorkflow,
        ApprovalLog,
        ApprovalDecision,
        ApprovalNotification
    )
except ImportError:
    # Fallback if approval_workflow models are not yet defined
    ApprovalWorkflow = None
    ApprovalLog = None
    ApprovalDecision = None
    ApprovalNotification = None
from usermanagement.models import Organization
from usermanagement.utils import PermissionUtils
from accounting.mixins import UserOrganizationMixin
from utils.audit_logging import log_action

logger = logging.getLogger(__name__)


class ApprovalQueueView(UserOrganizationMixin, ListView):
    """
    Display pending approvals for current user.
    
    Permissions:
    - User must be logged in
    - Must be in a valid organization
    - Only shows journals assigned to user as approver
    
    Context:
    - pending_approvals: Journals waiting for user's approval
    - queue_stats: Queue statistics
    - filters_applied: Active filter names
    """
    
    template_name = 'accounting/approval/approval_queue.html'
    paginate_by = 25
    context_object_name = 'pending_approvals'

    def dispatch(self, request, *args, **kwargs):
        self.organization = self.get_organization()
        if not self.organization:
            messages.warning(request, _('Please select an active organization to continue.'))
            return redirect('usermanagement:select_organization')

        if not PermissionUtils.has_permission(request.user, self.organization, 'accounting', 'journal', 'approve_journal'):
            messages.error(request, _('You do not have permission to review approvals.'))
            return redirect('dashboard')

        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        """Get journals pending approval by current user."""
        user = self.request.user
        org = self.organization
        
        # Get all journals with pending approvals
        journals = Journal.objects.filter(
            approval_log__status=ApprovalLog.STATUS_PENDING,
            organization=org
        ).select_related(
            'journal_type',
            'approval_log__workflow',
            'created_by'
        ).prefetch_related(
            'approval_log__decisions',
            'lines'
        )
        
        # Filter only those where user is an approver
        pending_for_user = []
        for journal in journals:
            approvers = journal.approval_log.get_current_step_approvers()
            if user in approvers:
                pending_for_user.append(journal.id)
        
        journals = journals.filter(id__in=pending_for_user)
        
        # Apply filters
        status_filter = self.request.GET.get('status')
        if status_filter:
            journals = journals.filter(status=status_filter)
        
        journal_type_filter = self.request.GET.get('journal_type')
        if journal_type_filter:
            journals = journals.filter(journal_type_id=journal_type_filter)
        
        # Search
        search = self.request.GET.get('q')
        if search:
            journals = journals.filter(
                journal_number__icontains=search
            ) | journals.filter(
                description__icontains=search
            )
        
        # Sort
        sort_by = self.request.GET.get('sort', '-submitted_for_approval_at')
        journals = journals.order_by(sort_by)
        
        return journals
    
    def get_context_data(self, **kwargs):
        """Add queue statistics to context."""
        context = super().get_context_data(**kwargs)
        
        org = self.organization
        user = self.request.user
        
        # Queue statistics
        all_pending = Journal.objects.filter(
            approval_log__status=ApprovalLog.STATUS_PENDING,
            organization=org
        )
        
        stats = {
            'total_pending': all_pending.count(),
            'high_priority': sum(1 for j in all_pending if j.total_debit > 100000),
            'overdue': 0,  # Calculate based on timeout
            'assigned_to_me': self.object_list.count(),
        }
        
        # Check for overdue
        from datetime import timedelta
        cutoff_date = datetime.now() - timedelta(days=5)
        stats['overdue'] = all_pending.filter(
            approval_log__submitted_at__lt=cutoff_date
        ).count()
        
        context['queue_stats'] = stats
        context['journal_types'] = JournalType.objects.filter(
            organization=org,
            is_active=True
        )
        
        return context


class VoucherApproveView(UserOrganizationMixin, View):
    """
    Approve a journal at current step.
    
    Process:
    1. Verify user is authorized approver for journal
    2. Record approval decision
    3. Check if all required approvals obtained
    4. Move to next step or mark complete
    5. Send notifications
    6. Auto-post if workflow configured
    
    Returns:
    - HTML redirect to approval queue
    - HTMX JSON response with updated status
    """
    
    def post(self, request, journal_id):
        """Handle approval submission."""
        organization = self.get_organization()
        if not organization:
            messages.warning(request, _('Please select an active organization to continue.'))
            return redirect('usermanagement:select_organization')
        self.organization = organization

        journal = get_object_or_404(
            Journal,
            id=journal_id,
            organization=organization
        )

        if not PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'approve_journal'):
            messages.error(request, _('You do not have permission to approve journals.'))
            return redirect('accounting:approval_queue')
        
        # Verify user is authorized
        approval_log = getattr(journal, 'approval_log', None)
        if not approval_log or approval_log.status != ApprovalLog.STATUS_PENDING:
            messages.error(request, _('Journal is not pending approval'))
            return redirect('accounting:approval_queue')
        
        approvers = approval_log.get_current_step_approvers()
        if request.user not in approvers:
            messages.error(request, _('You are not authorized to approve this journal'))
            logger.warning(
                f"Unauthorized approval attempt by {request.user} for journal {journal_id}"
            )
            return redirect('accounting:approval_queue')
        
        # Get approval comments
        comments = request.POST.get('comments', '')
        
        try:
            with transaction.atomic():
                # Record approval decision
                step = approval_log.workflow.steps.filter(
                    step_order=approval_log.current_step
                ).first()
                
                decision = ApprovalDecision.objects.create(
                    approval_log=approval_log,
                    step=step,
                    approver=request.user,
                    decision=ApprovalDecision.DECISION_APPROVE,
                    comments=comments
                )
                
                # Check if all required approvals obtained for this step
                required_count = step.required_count if step else 1
                approve_count = approval_log.decisions.filter(
                    step=step,
                    decision=ApprovalDecision.DECISION_APPROVE
                ).count()
                
                if approve_count >= required_count:
                    # Mark step approved
                    approval_log.mark_step_approved(approval_log.current_step)
                    
                    # Move to next step
                    next_step = approval_log.workflow.steps.filter(
                        step_order=approval_log.current_step + 1
                    ).first()
                    
                    if next_step:
                        approval_log.current_step += 1
                        approval_log.save()
                        
                        # Notify next approvers
                        self._notify_next_approvers(approval_log, journal)
                    
                    elif approval_log.is_complete():
                        # All steps complete - mark approved
                        approval_log.status = ApprovalLog.STATUS_APPROVED
                        approval_log.completed_at = datetime.now()
                        approval_log.save()
                        
                        # Auto-post if configured
                        if approval_log.workflow.auto_post_after_approval:
                            journal.status = Journal.STATUS_POSTED
                            journal.save()
                            messages.success(
                                request,
                                _('Journal approved and posted successfully')
                            )
                        else:
                            messages.success(request, _('Journal approved successfully'))
                        
                        # Send completion notification
                        self._notify_completion(approval_log, journal)
                
                # Log action
                log_action(
                    user=request.user,
                    organization=self.organization,
                    action='approved_journal',
                    object_type='Journal',
                    object_id=journal.id,
                    details=f'Approved journal {journal.journal_number} at step {approval_log.current_step}'
                )
        
        except Exception as e:
            logger.exception(f"Error approving journal {journal_id}: {e}")
            messages.error(request, _('Error processing approval: %(error)s') % {'error': str(e)})
        
        return redirect('accounting:approval_queue')
    
    def _notify_next_approvers(self, approval_log, journal):
        """Send notification to next approvers."""
        approvers = approval_log.get_current_step_approvers()
        
        for approver in approvers:
            notification = ApprovalNotification.objects.create(
                approval_log=approval_log,
                recipient=approver,
                notification_type=ApprovalNotification.TYPE_NEEDS_APPROVAL
            )
            
            # Queue email
            self._send_approval_email(approver, journal, approval_log)
    
    def _notify_completion(self, approval_log, journal):
        """Send completion notification to submitter."""
        submitter = approval_log.submitted_by
        
        if submitter:
            notification = ApprovalNotification.objects.create(
                approval_log=approval_log,
                recipient=submitter,
                notification_type=ApprovalNotification.TYPE_APPROVED
            )
            
            # Queue email
            self._send_completion_email(submitter, journal)
    
    def _send_approval_email(self, user, journal, approval_log):
        """Send approval request email."""
        context = {
            'user': user,
            'journal': journal,
            'approval_log': approval_log,
            'approval_url': self.request.build_absolute_uri(
                reverse('accounting:approval_queue')
            )
        }
        
        subject = _('Action Required: Journal Approval - %(ref)s') % {
            'ref': journal.journal_number
        }
        message = render_to_string(
            'accounting/emails/approval_needed.txt',
            context
        )
        
        try:
            send_mail(
                subject,
                message,
                'noreply@erp.local',
                [user.email],
                fail_silently=False
            )
            logger.info(f"Approval email sent to {user.email}")
        except Exception as e:
            logger.error(f"Failed to send approval email: {e}")
    
    def _send_completion_email(self, user, journal):
        """Send approval completion email."""
        context = {
            'user': user,
            'journal': journal,
            'journal_url': self.request.build_absolute_uri(
                reverse('accounting:voucher_detail', args=[journal.id])
            )
        }
        
        subject = _('Journal Approved - %(ref)s') % {
            'ref': journal.journal_number
        }
        message = render_to_string(
            'accounting/emails/approval_complete.txt',
            context
        )
        
        try:
            send_mail(
                subject,
                message,
                'noreply@erp.local',
                [user.email],
                fail_silently=False
            )
            logger.info(f"Approval completion email sent to {user.email}")
        except Exception as e:
            logger.error(f"Failed to send completion email: {e}")


class VoucherRejectView(UserOrganizationMixin, View):
    """
    Reject a journal at current step.
    
    Process:
    1. Verify user is authorized approver
    2. Record rejection decision with reason
    3. Move journal back to "Pending Review" status
    4. Send notification to submitter
    5. Allow resubmission
    """
    
    def post(self, request, journal_id):
        """Handle rejection submission."""
        organization = self.get_organization()
        if not organization:
            messages.warning(request, _('Please select an active organization to continue.'))
            return redirect('usermanagement:select_organization')
        self.organization = organization

        journal = get_object_or_404(
            Journal,
            id=journal_id,
            organization=organization
        )

        if not PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'reject_journal'):
            messages.error(request, _('You do not have permission to reject journals.'))
            return redirect('accounting:approval_queue')

        approval_log = getattr(journal, 'approval_log', None)
        if not approval_log or approval_log.status != ApprovalLog.STATUS_PENDING:
            messages.error(request, _('Journal is not pending approval'))
            return redirect('accounting:approval_queue')
        
        approvers = approval_log.get_current_step_approvers()
        if request.user not in approvers:
            messages.error(request, _('You are not authorized to reject this journal'))
            return redirect('accounting:approval_queue')
        
        reason = request.POST.get('reason', '')
        if not reason:
            messages.error(request, _('Rejection reason is required'))
            return redirect('accounting:approval_queue')
        
        try:
            with transaction.atomic():
                # Record rejection decision
                step = approval_log.workflow.steps.filter(
                    step_order=approval_log.current_step
                ).first()
                
                ApprovalDecision.objects.create(
                    approval_log=approval_log,
                    step=step,
                    approver=request.user,
                    decision=ApprovalDecision.DECISION_REJECT,
                    comments=reason
                )
                
                # Mark approval as rejected
                approval_log.status = ApprovalLog.STATUS_REJECTED
                approval_log.rejection_reason = reason
                approval_log.completed_at = datetime.now()
                approval_log.save()
                
                # Reset journal to draft
                journal.status = Journal.STATUS_DRAFT
                journal.save()
                
                # Send rejection email
                self._send_rejection_email(
                    approval_log.submitted_by,
                    journal,
                    reason
                )
                
                # Log action
                log_action(
                    user=request.user,
                    organization=self.organization,
                    action='rejected_journal',
                    object_type='Journal',
                    object_id=journal.id,
                    details=f'Rejected journal {journal.journal_number}: {reason}'
                )
                
                messages.success(request, _('Journal rejected successfully'))
        
        except Exception as e:
            logger.exception(f"Error rejecting journal {journal_id}: {e}")
            messages.error(request, _('Error processing rejection'))
        
        return redirect('accounting:approval_queue')
    
    def _send_rejection_email(self, user, journal, reason):
        """Send rejection email."""
        if not user:
            return
        
        context = {
            'user': user,
            'journal': journal,
            'reason': reason,
            'journal_url': self.request.build_absolute_uri(
                reverse('accounting:voucher_edit', args=[journal.id])
            )
        }
        
        subject = _('Journal Rejected - %(ref)s') % {
            'ref': journal.journal_number
        }
        message = render_to_string(
            'accounting/emails/approval_rejected.txt',
            context
        )
        
        try:
            send_mail(
                subject,
                message,
                'noreply@erp.local',
                [user.email],
                fail_silently=False
            )
        except Exception as e:
            logger.error(f"Failed to send rejection email: {e}")


class ApprovalHistoryView(UserOrganizationMixin, DetailView):
    """
    Display approval history for a journal.
    
    Shows:
    - All approval decisions
    - Step status
    - Approver comments
    - Timeline of approvals
    """
    
    template_name = 'accounting/approval/approval_history.html'
    context_object_name = 'journal'

    def dispatch(self, request, *args, **kwargs):
        self.organization = self.get_organization()
        if not self.organization:
            messages.warning(request, _('Please select an active organization to continue.'))
            return redirect('usermanagement:select_organization')

        if not PermissionUtils.has_permission(request.user, self.organization, 'accounting', 'journal', 'view'):
            messages.error(request, _('You do not have permission to view approval history.'))
            return redirect('dashboard')

        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        """Get journal with approval details."""
        return Journal.objects.filter(
            organization=self.organization,
            approval_log__isnull=False
        ).select_related('approval_log__workflow').prefetch_related(
            'approval_log__decisions'
        )
    
    def get_context_data(self, **kwargs):
        """Add approval history to context."""
        context = super().get_context_data(**kwargs)
        journal = self.object
        
        if hasattr(journal, 'approval_log'):
            approval_log = journal.approval_log
            context['approval_log'] = approval_log
            context['decisions'] = approval_log.decisions.select_related(
                'step',
                'approver'
            ).order_by('decided_at')
        
        return context


class ApprovalDashboardView(UserOrganizationMixin, View):
    """
    Dashboard with approval statistics and metrics.
    
    Displays:
    - Total pending approvals
    - Overdue approvals
    - Approval completion rate
    - Per-user approval metrics
    - Workflow performance
    """
    
    template_name = 'accounting/approval/approval_dashboard.html'
    
    def get(self, request):
        """Display approval dashboard."""
        org = self.get_organization()
        if not org:
            messages.warning(request, _('Please select an active organization to continue.'))
            return redirect('usermanagement:select_organization')
        self.organization = org

        if not PermissionUtils.has_permission(request.user, org, 'accounting', 'journal', 'approve_journal'):
            messages.error(request, _('You do not have permission to view the approval dashboard.'))
            return redirect('dashboard')

        user = request.user
        
        # Get all approval logs for organization
        all_approvals = ApprovalLog.objects.filter(
            journal__organization=org
        )
        
        # Statistics
        stats = {
            'total_pending': all_approvals.filter(
                status=ApprovalLog.STATUS_PENDING
            ).count(),
            'total_approved': all_approvals.filter(
                status=ApprovalLog.STATUS_APPROVED
            ).count(),
            'total_rejected': all_approvals.filter(
                status=ApprovalLog.STATUS_REJECTED
            ).count(),
            'avg_approval_time': self._calculate_avg_approval_time(all_approvals),
            'approval_rate': self._calculate_approval_rate(all_approvals),
        }
        
        # Per-user stats
        per_user_stats = self._calculate_per_user_stats(org)
        
        # Workflow performance
        workflow_stats = self._calculate_workflow_stats(org)
        
        context = {
            'stats': stats,
            'per_user_stats': per_user_stats,
            'workflow_stats': workflow_stats,
            'pending_approvals': all_approvals.filter(
                status=ApprovalLog.STATUS_PENDING
            ).count(),
        }
        
        return render(request, self.template_name, context)
    
    def _calculate_avg_approval_time(self, approvals):
        """Calculate average time for approval."""
        completed = approvals.filter(
            status=ApprovalLog.STATUS_APPROVED,
            completed_at__isnull=False
        )
        
        if not completed:
            return 0
        
        total_time = 0
        for log in completed:
            delta = log.completed_at - log.submitted_at
            total_time += delta.total_seconds()
        
        return int(total_time / len(completed) / 3600)  # Hours
    
    def _calculate_approval_rate(self, approvals):
        """Calculate approval vs rejection rate."""
        approved = approvals.filter(status=ApprovalLog.STATUS_APPROVED).count()
        rejected = approvals.filter(status=ApprovalLog.STATUS_REJECTED).count()
        total = approved + rejected
        
        if total == 0:
            return 0
        
        return int((approved / total) * 100)
    
    def _calculate_per_user_stats(self, org):
        """Calculate approval stats per user."""
        from django.db.models import Count, Q
        from usermanagement.models import UserOrganization
        
        users = UserOrganization.objects.filter(
            organization=org
        ).values_list('user_id', flat=True)
        
        user_stats = []
        for user_id in users:
            from django.contrib.auth.models import User
            user = User.objects.get(id=user_id)
            
            decisions = ApprovalDecision.objects.filter(
                approver=user,
                approval_log__journal__organization=org
            )
            
            user_stats.append({
                'user': user,
                'approved': decisions.filter(decision=ApprovalDecision.DECISION_APPROVE).count(),
                'rejected': decisions.filter(decision=ApprovalDecision.DECISION_REJECT).count(),
            })
        
        return user_stats
    
    def _calculate_workflow_stats(self, org):
        """Calculate stats per workflow."""
        workflows = ApprovalWorkflow.objects.filter(
            organization=org
        )
        
        workflow_stats = []
        for workflow in workflows:
            logs = ApprovalLog.objects.filter(workflow=workflow)
            
            workflow_stats.append({
                'workflow': workflow,
                'total': logs.count(),
                'approved': logs.filter(status=ApprovalLog.STATUS_APPROVED).count(),
                'rejected': logs.filter(status=ApprovalLog.STATUS_REJECTED).count(),
                'pending': logs.filter(status=ApprovalLog.STATUS_PENDING).count(),
            })
        
        return workflow_stats
