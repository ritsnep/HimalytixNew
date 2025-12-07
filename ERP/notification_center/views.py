from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpRequest
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.shortcuts import render, redirect
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .models import InAppNotification, ApprovalRequest


def _serialize_notification(notification: InAppNotification) -> dict:
    return {
        "id": notification.id,
        "title": notification.title,
        "body": notification.body,
        "is_read": notification.is_read,
        "created_at": notification.created_at.isoformat(),
        "created_display": notification.created_at.strftime("%b %d, %H:%M"),
    }


@login_required
@require_GET
@ensure_csrf_cookie
def notification_list(request: HttpRequest):
    """Return the user's latest notifications."""
    try:
        limit = int(request.GET.get("limit", 15))
    except (TypeError, ValueError):
        limit = 15
    limit = max(1, min(limit, 50))  # Clamp to sensible bounds
    qs = InAppNotification.objects.filter(recipient=request.user).order_by("-created_at")
    items = list(qs[:limit])
    unread_count = qs.filter(is_read=False).count()
    return JsonResponse(
        {
            "items": [_serialize_notification(item) for item in items],
            "unread_count": unread_count,
        }
    )


@login_required
@require_POST
def notification_mark_read(request: HttpRequest, pk: int):
    notification = get_object_or_404(
        InAppNotification, pk=pk, recipient=request.user
    )
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["is_read", "read_at"])
    return JsonResponse({"ok": True, "id": notification.id})


@login_required
@require_POST
def notification_mark_all_read(request: HttpRequest):
    qs = InAppNotification.objects.filter(recipient=request.user, is_read=False)
    updated = qs.update(is_read=True, read_at=timezone.now())
    return JsonResponse({"ok": True, "updated": updated})


# Approval request detail/decision
@login_required
def approval_detail(request: HttpRequest, pk: int):
    approval = get_object_or_404(ApprovalRequest, pk=pk)
    can_act = approval.is_open and (
        (approval.approver_id == request.user.id)
        or request.user.is_staff
        or request.user.is_superuser
    )
    context = {
        "approval": approval,
        "can_act": can_act,
        "metadata": approval.metadata or {},
    }
    return render(request, "notification_center/approval_detail.html", context)


@login_required
@require_POST
def approval_decision(request: HttpRequest, pk: int):
    approval = get_object_or_404(ApprovalRequest, pk=pk)
    decision = request.POST.get("decision")
    notes = request.POST.get("notes", "")
    if not approval.is_open:
        return redirect("notification_center:approval_detail", pk=pk)
    if approval.approver_id and approval.approver_id != request.user.id and not request.user.is_staff:
        return redirect("notification_center:approval_detail", pk=pk)

    if decision == "approve":
        approval.approve(notes=notes)
    elif decision == "reject":
        approval.reject(notes=notes)
    return redirect("notification_center:approval_detail", pk=pk)
