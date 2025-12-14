from unittest import mock

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from accounting.models import AuditLog
from accounting.tests import factories as f
from accounting.utils.audit import log_audit_event
from configuration.models import ConfigurationEntry
from configuration.services import ConfigurationService


class LogAuditEventTests(TestCase):
    def setUp(self):
        self.organization = f.create_organization()
        self.user = f.create_user(organization=self.organization)
        self.journal = f.create_journal(organization=self.organization, created_by=self.user)

    def test_log_audit_event_records_changes_and_org(self):
        entry = log_audit_event(
            self.user,
            self.journal,
            "update",
            before_state={"status": "draft", "total_debit": 0},
            after_state={"status": "posted", "total_debit": 100},
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry.organization, self.organization)
        self.assertEqual(entry.changes["status"]["old"], "draft")
        self.assertEqual(entry.changes["status"]["new"], "posted")
        self.assertEqual(entry.changes["total_debit"]["new"], 100)

    @mock.patch("accounting.tasks.log_audit_event_async.delay")
    def test_log_audit_event_async_delegates_to_task(self, mock_delay):
        log_audit_event(
            self.user,
            self.journal,
            "update",
            changes={"status": {"old": "draft", "new": "posted"}},
            async_write=True,
        )
        content_type = ContentType.objects.get_for_model(self.journal)
        mock_delay.assert_called_once_with(
            self.user.pk,
            "update",
            content_type.pk,
            self.journal.pk,
            changes={"status": {"old": "draft", "new": "posted"}},
            details=None,
            ip_address=None,
            organization_id=self.organization.pk,
        )


class ConfigurationAuditLoggingTests(TestCase):
    def setUp(self):
        self.organization = f.create_organization()
        self.user = f.create_user(organization=self.organization)

    def test_set_value_writes_audit_entry(self):
        entry = ConfigurationService.set_value(
            organization=self.organization,
            scope=ConfigurationEntry.SCOPE_FINANCE,
            key="base_currency",
            value="BRL",
            user=self.user,
        )
        ct = ContentType.objects.get_for_model(entry)
        audit_entry = AuditLog.objects.filter(
            content_type=ct,
            object_id=entry.pk,
        ).latest("timestamp")
        self.assertEqual(audit_entry.organization, self.organization)
        self.assertEqual(audit_entry.changes["value"]["new"], "BRL")
