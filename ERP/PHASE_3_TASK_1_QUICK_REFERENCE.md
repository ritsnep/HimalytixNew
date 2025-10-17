# Phase 3 Task 1: Quick Reference

## Files Created

### Models (accounting/models/approval_workflow.py)
- `ApprovalWorkflow` - Define approval rules
- `ApprovalStep` - Individual workflow steps
- `ApprovalLog` - Track approval history
- `ApprovalDecision` - Individual decisions
- `ApprovalNotification` - Notification queue

### Views (accounting/views/approval_workflow.py)
- `ApprovalQueueView` - List pending approvals
- `VoucherApproveView` - Process approval
- `VoucherRejectView` - Process rejection
- `ApprovalHistoryView` - View approval timeline
- `ApprovalDashboardView` - Analytics dashboard

### URLs (accounting/urls/approval_urls.py)
- `/queue/` - Approval queue
- `/dashboard/` - Dashboard
- `/<id>/approve/` - Approve
- `/<id>/reject/` - Reject
- `/<id>/history/` - History

### Templates
- `approval_queue.html` - Queue UI
- `approval_history.html` - Timeline UI
- `approval_dashboard.html` - Dashboard UI

### Emails
- `approval_needed.txt` - Notify approvers
- `approval_complete.txt` - Notify completion
- `approval_rejected.txt` - Notify rejection

### Tests (accounting/tests/test_approval_workflow.py)
- `ApprovalWorkflowModelTests` (5 tests)
- `ApprovalQueueViewTests` (3 tests)
- `VoucherApproveViewTests` (4 tests)
- `VoucherRejectViewTests` (3 tests)
- `SequentialApprovalWorkflowTests` (2 tests)
- `ParallelApprovalWorkflowTests` (1 test)

---

## Key Concepts

### ApprovalWorkflow
Define how journals should be approved:
```python
workflow = ApprovalWorkflow.objects.create(
    name='Standard Approval',
    code='STD',
    organization=org,
    approval_type='sequential',  # or 'parallel'
    auto_post_after_approval=True,
)
```

### ApprovalStep
Define a step in the workflow:
```python
step = ApprovalStep.objects.create(
    workflow=workflow,
    step_order=1,
    name='Manager Review',
    required_count=1,
    timeout_days=3,
)
step.approvers.add(manager)
```

### ApprovalLog
Track approval for a journal:
```python
log = ApprovalLog.objects.create(
    journal=journal,
    workflow=workflow,
    submitted_by=user,
)
```

### ApprovalDecision
Record an approval decision:
```python
decision = ApprovalDecision.objects.create(
    approval_log=log,
    approver=user,
    decision='approve',  # or 'reject'
    comments='Looks good',
)
```

---

## Common Tasks

### Submit Journal for Approval
```python
workflow = ApprovalWorkflow.objects.get(code='STD', organization=org)
approval_log = ApprovalLog.objects.create(
    journal=journal,
    workflow=workflow,
    submitted_by=request.user,
)
```

### Approve a Journal
```python
decision = ApprovalDecision.objects.create(
    approval_log=approval_log,
    approver=request.user,
    decision=ApprovalDecision.DECISION_APPROVE,
    comments='Approved',
)
approval_log.mark_step_approved(approval_log.current_step)
```

### Reject a Journal
```python
decision = ApprovalDecision.objects.create(
    approval_log=approval_log,
    approver=request.user,
    decision=ApprovalDecision.DECISION_REJECT,
    comments='Please revise amounts',
)
approval_log.status = ApprovalLog.STATUS_REJECTED
approval_log.save()
```

### Get Pending Approvals for User
```python
approvals = Journal.objects.filter(
    approval_log__status='pending',
    approval_log__workflow__steps__approvers=user,
).distinct()
```

### Get Approval History for Journal
```python
decisions = journal.approval_log.decisions.select_related(
    'step', 'approver'
).order_by('decided_at')
```

### Check if Approval Complete
```python
if journal.approval_log.is_complete():
    journal.status = Journal.STATUS_POSTED
    journal.save()
```

---

## URL Patterns

```python
# In main urls.py:
path('approval/', include('accounting.urls.approval_urls')),

# Results in:
/approval/queue/                   - List pending
/approval/dashboard/               - Dashboard
/approval/123/approve/             - POST to approve
/approval/123/reject/              - POST to reject
/approval/123/history/             - View history
```

---

## Database Queries

### Create Workflow with Steps
```python
workflow = ApprovalWorkflow.objects.create(
    name='Multi-Level',
    code='MULTI',
    organization=org,
)

# Step 1
step1 = ApprovalStep.objects.create(
    workflow=workflow,
    step_order=1,
    name='Manager',
    required_count=1,
)
step1.approvers.add(manager)

# Step 2
step2 = ApprovalStep.objects.create(
    workflow=workflow,
    step_order=2,
    name='Director',
    required_count=1,
)
step2.approvers.add(director)
```

### Query Pending Approvals
```python
pending = ApprovalLog.objects.filter(
    status=ApprovalLog.STATUS_PENDING,
    journal__organization=org,
).select_related('journal', 'workflow')
```

### Query Approval Statistics
```python
stats = {
    'total': ApprovalLog.objects.count(),
    'approved': ApprovalLog.objects.filter(
        status=ApprovalLog.STATUS_APPROVED
    ).count(),
    'rejected': ApprovalLog.objects.filter(
        status=ApprovalLog.STATUS_REJECTED
    ).count(),
}
```

---

## Migration

```bash
# Create migration
python manage.py makemigrations accounting

# Run migration
python manage.py migrate accounting

# Check migration
python manage.py showmigrations accounting
```

---

## Testing

```bash
# Run all approval tests
python manage.py test accounting.tests.test_approval_workflow

# Run specific test class
python manage.py test \
    accounting.tests.test_approval_workflow.VoucherApproveViewTests

# Run with coverage
coverage run --source='accounting' manage.py test approval_workflow
coverage report
```

---

## Template Usage

### In approval_queue.html
```django
{% for journal in pending_approvals %}
    <tr>
        <td>{{ journal.reference_no }}</td>
        <td>{{ journal.total_debit|floatformat:2 }}</td>
        <td>
            <button class="btn btn-success" data-bs-toggle="modal"
                    data-bs-target="#approveModal{{ journal.id }}">
                Approve
            </button>
        </td>
    </tr>
{% endfor %}
```

### In base_voucher.html (to add approval link)
```django
{% if journal.approval_log %}
    <a href="{% url 'accounting:approval_history' journal.id %}" class="btn btn-info">
        View Approvals
    </a>
{% else %}
    <form method="post" action="{% url 'approval:submit' journal.id %}">
        {% csrf_token %}
        <button type="submit" class="btn btn-primary">
            Submit for Approval
        </button>
    </form>
{% endif %}
```

---

## Email Sending

### Configure Email
```python
# settings.py
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your@gmail.com'
EMAIL_HOST_PASSWORD = 'your-app-password'
```

### Send Email
```python
from django.core.mail import send_mail
from django.template.loader import render_to_string

context = {'user': user, 'journal': journal}
subject = 'Action Required: Journal Approval'
message = render_to_string(
    'accounting/emails/approval_needed.txt',
    context
)
send_mail(subject, message, 'noreply@erp.local', [user.email])
```

---

## Admin Configuration

### Register Models
```python
# accounting/admin.py
from accounting.models.approval_workflow import *

@admin.register(ApprovalWorkflow)
class ApprovalWorkflowAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'approval_type')
    list_filter = ('is_active', 'approval_type', 'organization')
    search_fields = ('name', 'code')
    filter_horizontal = ('steps',)

@admin.register(ApprovalStep)
class ApprovalStepAdmin(admin.ModelAdmin):
    list_display = ('workflow', 'step_order', 'name', 'required_count')
    list_filter = ('workflow', 'step_order')
    filter_horizontal = ('approvers',)

@admin.register(ApprovalLog)
class ApprovalLogAdmin(admin.ModelAdmin):
    list_display = ('journal', 'workflow', 'status', 'submitted_at')
    list_filter = ('status', 'workflow', 'submitted_at')
    readonly_fields = ('submitted_at', 'completed_at')

@admin.register(ApprovalDecision)
class ApprovalDecisionAdmin(admin.ModelAdmin):
    list_display = ('approval_log', 'approver', 'decision', 'decided_at')
    list_filter = ('decision', 'decided_at')
    readonly_fields = ('decided_at',)
```

---

## Views Integration

### Add to VoucherDetailView
```python
def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['approval_log'] = getattr(
        self.object, 'approval_log', None
    )
    return context
```

### Add to VoucherListView Queryset
```python
def get_queryset(self):
    qs = super().get_queryset()
    return qs.select_related('approval_log__workflow')
```

---

## Status Codes

```python
# ApprovalLog Status
STATUS_PENDING = 'pending'
STATUS_APPROVED = 'approved'
STATUS_REJECTED = 'rejected'
STATUS_ESCALATED = 'escalated'

# ApprovalDecision Type
DECISION_APPROVE = 'approve'
DECISION_REJECT = 'reject'

# ApprovalNotification Type
TYPE_SUBMITTED = 'submitted'
TYPE_NEEDS_APPROVAL = 'needs_approval'
TYPE_APPROVED = 'approved'
TYPE_REJECTED = 'rejected'
TYPE_ESCALATED = 'escalated'
```

---

## Troubleshooting

### Approval not showing in queue
- Check if user is assigned approver
- Check if workflow is active
- Check organization isolation

### Email not sending
- Check EMAIL_BACKEND configuration
- Check SMTP credentials
- Check recipient email validity

### Status not updating
- Call `mark_step_approved()` after recording decision
- Check if required_count is met
- Refresh object from database

### Permission denied
- Verify user is approver for current step
- Check organization membership
- Check workflow assignment

---

## Performance Tips

1. Use `select_related()` for foreign keys
2. Use `prefetch_related()` for many-to-many
3. Add indexes on status fields
4. Use pagination for large queues
5. Async email sending with Celery

---

## Next Steps

After Task 1, proceed with:
1. **Task 5:** Performance Optimization (index/cache)
2. **Task 2:** Advanced Reporting
3. **Task 6:** i18n Internationalization
4. **Task 3-4, 7-8:** Other features

---

## Support

For issues or questions:
1. Check PHASE_3_TASK_1_COMPLETE.md for detailed docs
2. Review test cases for usage examples
3. Check model docstrings for API details
4. Review view source for implementation patterns

---

**Status: ✅ Complete and Production Ready**
