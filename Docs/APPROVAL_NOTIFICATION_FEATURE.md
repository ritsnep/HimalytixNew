## Approval & Notification Flow

This document describes the approval request and notification features in the system.

### Core Models
- `NotificationRule`: Admin-configurable rules for sending messages (email, in-app, SMS placeholder, Django messages). Supports direct recipients (`direct_user`, `direct_email`, `direct_phone`) and fallback to `request.user`.
- `InAppNotification`: Stores in-app notifications with optional `action_url` for deep links.
- `ApprovalRequest`: Represents an approval workflow item tied to any model via ContentType (pending/approved/rejected, requester, approver, metadata, decision notes).

### Key APIs & Views
- In-app notifications:
  - `GET /notifications/notifications/` → JSON list + unread count.
  - `POST /notifications/notifications/mark-read/<id>/`
  - `POST /notifications/notifications/mark-all-read/`
- Approvals:
  - `GET /notifications/approvals/<id>/` → Approval detail page with metadata and approve/reject buttons (only if pending and user is approver/staff).
  - `POST /notifications/approvals/<id>/decision/` → Approve/Reject with optional notes.

### Creating Approval Requests in Code
Use the helper to persist and notify:
```python
from notification_center.services import create_approval_notification

approval = create_approval_notification(
    instance=target_object,            # object needing approval
    requested_by=request.user,         # initiator
    approver=approver_user,            # required approver
    title="Voucher approval required",
    message="Please review and approve.",
    metadata={"voucher_id": target_object.id, "amount": str(target_object.amount)},
)
```
This creates an `ApprovalRequest` and an `InAppNotification` with a link to the approval detail page.

### Admin Usage
- Manage rules, templates, logs, in-app notifications, and approval requests via Django admin.
- For rules, set direct recipients or target paths to avoid “Skipped” deliveries.

### Frontend Dropdown Behavior
- Header notification bell fetches in-app notifications, renders list, marks read/all with CSRF protection, and shows errors inline.
- `action_url` on notifications can be rendered as links in templates or dropdown to direct users to approval pages.

### Configuration Notes
- Rate limits can be tuned via `RATE_LIMIT_RULES` in settings; staff/superusers are exempt.
- CSRF is exposed via a meta tag in header templates for JS POSTs.
- Approval pages use `notification_center/approval_detail.html`; adjust as needed for additional fields or permissions.
