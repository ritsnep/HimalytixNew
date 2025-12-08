from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
import os
import logging
logger = logging.getLogger(__name__)

from django.contrib.contenttypes.models import ContentType
from .models import (
    InAppNotification,
    MessageTemplate,
    NotificationLog,
    NotificationRule,
)
from .services import capture_initial_state, dispatch_for_instance, get_rules_for_model

# Avoid recursive triggers on framework tables; Transaction remains observable.
EXCLUDED_SENDERS = {NotificationRule, NotificationLog, MessageTemplate, InAppNotification, ContentType}


if os.environ.get('DISABLE_NOTIFICATION_SIGNALS') != '1':
    @receiver(pre_save)
    def notification_pre_save(sender, instance, raw: bool = False, **kwargs):
        if raw or sender in EXCLUDED_SENDERS:
            return
        try:
            rules = get_rules_for_model(sender)
        except Exception:
            # If ContentType table isn't ready, or any DB error occurs while
            # trying to obtain rules, skip notifications to avoid crashing
            # management commands or tests during migrations.
            return
        if not rules:
            return
        instance.__notification_initial__ = capture_initial_state(instance, rules)


    @receiver(post_save)
    def notification_post_save(sender, instance, created: bool, raw: bool = False, **kwargs):
        if raw or sender in EXCLUDED_SENDERS:
            return
        try:
            dispatch_for_instance(instance, created=created)
        except Exception:
            # Catch unexpected failures to avoid breaking saves/management tasks
            logger.exception("Unhandled error in notification dispatch for %s", sender)
