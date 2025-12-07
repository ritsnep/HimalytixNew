from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import (
    InAppNotification,
    MessageTemplate,
    NotificationLog,
    NotificationRule,
)
from .services import capture_initial_state, dispatch_for_instance, get_rules_for_model

# Avoid recursive triggers on framework tables; Transaction remains observable.
EXCLUDED_SENDERS = {NotificationRule, NotificationLog, MessageTemplate, InAppNotification}


@receiver(pre_save)
def notification_pre_save(sender, instance, raw: bool = False, **kwargs):
    if raw or sender in EXCLUDED_SENDERS:
        return
    rules = get_rules_for_model(sender)
    if not rules:
        return
    instance.__notification_initial__ = capture_initial_state(instance, rules)


@receiver(post_save)
def notification_post_save(sender, instance, created: bool, raw: bool = False, **kwargs):
    if raw or sender in EXCLUDED_SENDERS:
        return
    dispatch_for_instance(instance, created=created)
