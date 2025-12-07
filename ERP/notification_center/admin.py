from django.contrib import admin
from django.utils.html import format_html

from django.contrib.contenttypes.models import ContentType
from django.contrib.admin.sites import AlreadyRegistered

try:
    from django.contrib.contenttypes.admin import ContentTypeAdmin  # Django >=3.2
except ImportError:  # Fallback for environments without the default admin class
    class ContentTypeAdmin(admin.ModelAdmin):
        search_fields = ("app_label", "model")

from .forms import NotificationRuleForm
from .models import (
    ApprovalRequest,
    InAppNotification,
    MessageTemplate,
    NotificationLog,
    NotificationRule,
    Transaction,
)
from .services import capture_initial_state, dispatch_single_rule

# Ensure ContentType admin is available for autocomplete_fields
try:
    admin.site.register(ContentType, ContentTypeAdmin)
except AlreadyRegistered:
    pass


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "channel", "updated_at")
    search_fields = ("name", "description", "subject", "body")
    readonly_fields = ("preview_with_sample", "created_at", "updated_at")
    fieldsets = (
        ("Meta", {"fields": ("name", "description", "channel", "is_html")}),
        (
            "Content",
            {"fields": ("subject", "body", "sample_context", "preview_with_sample")},
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def preview_with_sample(self, obj):
        if not obj.pk:
            return "Save the template to see a preview."
        if not obj.sample_context:
            return "Add a sample_context JSON to preview rendering."
        subject, body = obj.render(obj.sample_context)
        return format_html(
            "<strong>{}</strong><div style='white-space:pre-wrap;margin-top:6px'>{}</div>",
            subject or "(no subject)",
            body or "(empty body)",
        )

    preview_with_sample.short_description = "Preview"


@admin.register(NotificationRule)
class NotificationRuleAdmin(admin.ModelAdmin):
    form = NotificationRuleForm
    list_display = (
        "name",
        "content_type",
        "trigger",
        "status_field",
        "from_status",
        "to_status",
        "template",
        "is_active",
        "last_triggered_at",
    )
    list_filter = ("trigger", "is_active", "content_type")
    search_fields = ("name", "description", "to_status", "from_status")
    actions = ["simulate_trigger"]
    autocomplete_fields = ("content_type", "template", "created_by")

    @admin.action(description="Simulate trigger on latest object")
    def simulate_trigger(self, request, queryset):
        fired = 0
        for rule in queryset:
            model = rule.content_type.model_class()
            if model is None:
                continue
            instance = model.objects.order_by("-pk").first()
            if not instance:
                continue
            initial_state = capture_initial_state(instance, [rule])
            logs = dispatch_single_rule(
                rule,
                instance,
                request=request,
                extra_context={"admin_simulation": True, "initial_state": initial_state},
            )
            fired += len(logs)
        self.message_user(
            request,
            f"Simulated {fired} notification(s) from {queryset.count()} rule(s).",
        )


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "rule",
        "channel",
        "status",
        "recipient",
        "rendered_subject",
    )
    list_filter = ("status", "channel", "rule")
    search_fields = ("recipient", "rendered_subject", "rendered_body", "detail")
    readonly_fields = (
        "rule",
        "template",
        "content_type",
        "object_id",
        "channel",
        "status",
        "recipient",
        "rendered_subject",
        "rendered_body",
        "detail",
        "created_at",
    )


@admin.register(InAppNotification)
class InAppNotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "recipient", "is_read", "created_at", "action_url")
    list_filter = ("is_read", "created_at")
    search_fields = ("title", "body", "recipient__username", "recipient__email")
    actions = ["mark_as_read"]

    @admin.action(description="Mark selected notifications as read")
    def mark_as_read(self, request, queryset):
        updated = 0
        for notification in queryset:
            if not notification.is_read:
                notification.mark_read()
                updated += 1
        self.message_user(request, f"Marked {updated} notification(s) as read.")


@admin.register(ApprovalRequest)
class ApprovalRequestAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "approver", "requested_by", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("title", "message", "metadata")
    autocomplete_fields = ("approver", "requested_by", "content_type")
    readonly_fields = ("decided_at", "created_at", "updated_at")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("reference", "status_badge", "amount", "user", "updated_at")
    list_filter = ("status",)
    search_fields = ("reference", "description", "user__username", "user__email")
    readonly_fields = ("created_at", "updated_at")
    actions = ["mark_processing", "mark_completed", "mark_failed"]
    fieldsets = (
        ("Core", {"fields": ("reference", "amount", "status", "description", "metadata")}),
        ("Ownership", {"fields": ("user",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    @admin.action(description="Mark selected as processing (triggers rules)")
    def mark_processing(self, request, queryset):
        self._transition_status(queryset, Transaction.Status.PROCESSING)
        self.message_user(request, "Moved selected transactions to Processing.")

    @admin.action(description="Mark selected as completed (triggers rules)")
    def mark_completed(self, request, queryset):
        self._transition_status(queryset, Transaction.Status.COMPLETED)
        self.message_user(request, "Moved selected transactions to Completed.")

    @admin.action(description="Mark selected as failed (triggers rules)")
    def mark_failed(self, request, queryset):
        self._transition_status(queryset, Transaction.Status.FAILED)
        self.message_user(request, "Moved selected transactions to Failed.")

    def _transition_status(self, queryset, status_value: str) -> None:
        for tx in queryset:
            tx.status = status_value
            tx.save(update_fields=["status", "updated_at"])

    def status_badge(self, obj):
        color_map = {
            Transaction.Status.PENDING: "#999",
            Transaction.Status.PROCESSING: "#0d6efd",
            Transaction.Status.COMPLETED: "#198754",
            Transaction.Status.FAILED: "#dc3545",
            Transaction.Status.CANCELLED: "#6c757d",
        }
        color = color_map.get(obj.status, "#444")
        return format_html(
            "<span style='color:{};font-weight:600'>{}</span>",
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"
    status_badge.admin_order_field = "status"
