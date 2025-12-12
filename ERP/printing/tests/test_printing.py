from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.http import Http404
from django.test import Client, TestCase
from django.urls import reverse


class DummyLine:
    def __init__(
        self,
        account="Account1",
        description="Desc1",
        department="DeptA",
        cost_center="CC100",
        tax_amount=0,
        debit_amount=100,
        credit_amount=0,
    ):
        self.account = account
        self.description = description
        self.department = department
        self.cost_center = cost_center
        self.tax_amount = tax_amount
        self.debit_amount = debit_amount
        self.credit_amount = credit_amount


class DummyJournal:
    def __init__(self, jid=1):
        self.journal_id = jid
        self.pk = jid
        self.journal_number = str(jid)
        self.journal_date = "2025-01-01"

        self._lines = [
            DummyLine(
                account="Cash",
                description="Payment",
                department="HR",
                cost_center="1001",
                tax_amount=0,
                debit_amount=500,
                credit_amount=0,
            ),
            DummyLine(
                account="Expense",
                description="Meal",
                department="HR",
                cost_center="1001",
                tax_amount=50,
                debit_amount=0,
                credit_amount=500,
            ),
        ]

        class LineManager:
            def __init__(inner_self, outer):
                inner_self._outer = outer

            def select_related(inner_self, *args, **kwargs):
                return inner_self

            def all(inner_self):
                return inner_self._outer._lines

        self.lines = LineManager(self)


class PrintingAppTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user_with_perm = User.objects.create_user(username="permuser", password="pass123")
        self.user_without_perm = User.objects.create_user(username="nopermuser", password="pass123")

        perm = Permission.objects.get(codename="can_edit_print_templates")
        self.user_with_perm.user_permissions.add(perm)
        self.user_with_perm.refresh_from_db()

        self.client = Client()

        import printing.views as printing_views

        def dummy_get_object_or_404(model, *args, **kwargs):
            model_name = getattr(model, "__name__", None) or getattr(getattr(model, "model", None), "__name__", None)
            if model_name == "Journal" and kwargs.get("pk") == 1:
                return DummyJournal(jid=1)
            raise Http404("No such journal")

        self.getobj_patcher = patch.object(printing_views, "get_object_or_404", side_effect=dummy_get_object_or_404)
        self.getobj_patcher.start()

    def tearDown(self):
        self.getobj_patcher.stop()

    def test_preview_interface_by_permission(self):
        self.client.force_login(self.user_with_perm)
        url = reverse("print_preview", args=[1])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<form", msg_prefix="Config form not found in preview for permitted user")
        self.assertContains(response, 'name="template_name"', msg_prefix="Template selector not found for permitted user")
        self.assertContains(response, 'name="show_cost_center"', msg_prefix="Toggle checkboxes not found for permitted user")

        self.client.logout()
        self.client.force_login(self.user_without_perm)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<form", msg_prefix="Config form should not appear for non-permitted user")
        self.assertNotContains(response, 'name="template_name"', msg_prefix="Template selector should not appear for non-permitted user")
        self.assertContains(response, "Cash", msg_prefix="Journal content not visible to user without permission")

    def test_toggle_fields(self):
        self.client.force_login(self.user_with_perm)
        url = reverse("print_preview", args=[1])

        response = self.client.get(url)
        self.assertContains(response, "dim-costcenter", msg_prefix="Default preview should show cost center pill")

        post_data = {
            "template_name": "classic",
            "show_description": "on",
            "show_department": "on",
            "show_tax_column": "on",
            "show_audit": "on",
            "show_signatures": "on",
        }
        response = self.client.post(url, post_data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "dim-costcenter", msg_prefix="Cost center pill should be hidden after toggle off")
        self.assertContains(response, "dim-dept", msg_prefix="Department pill should still be visible when toggled on")

        from printing.models import PrintTemplateConfig

        config_obj = PrintTemplateConfig.objects.get(user=self.user_with_perm)
        self.assertFalse(config_obj.config.get("show_cost_center"), "Config should have show_cost_center=False after toggling off")
        self.assertTrue(config_obj.config.get("show_department"), "show_department should remain True in config")
        self.assertEqual(config_obj.template_name, "classic", "Template name should remain 'classic' after toggling fields")

    def test_switch_template(self):
        self.client.force_login(self.user_with_perm)
        url = reverse("print_preview", args=[1])

        response = self.client.get(url)
        self.assertContains(response, "template-classic", msg_prefix="Initial template should be classic by default")

        post_data = {
            "template_name": "compact",
            "show_description": "on",
            "show_department": "on",
            "show_cost_center": "on",
            "show_tax_column": "on",
            "show_audit": "on",
            "show_signatures": "on",
        }
        response = self.client.post(url, post_data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "template-compact", msg_prefix="After switching, template should be compact in output")
        self.assertNotContains(response, "Cost Center", msg_prefix="Avoid showing literal 'Cost Center' label text")
        self.assertContains(response, "CC:", msg_prefix="Compact layout should show 'CC:' label for cost center in line items")

        from printing.models import PrintTemplateConfig

        config_obj = PrintTemplateConfig.objects.get(user=self.user_with_perm)
        self.assertEqual(config_obj.template_name, "compact", "User's selected template should be saved as 'compact'")
        self.assertTrue(config_obj.config.get("show_cost_center"), "Toggles should remain saved (cost center should still be True)")

    def test_no_permission_cannot_save(self):
        self.client.force_login(self.user_without_perm)
        url = reverse("print_preview", args=[1])

        post_data = {
            "template_name": "compact",
            "show_description": "on",
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 403)

        from printing.models import PrintTemplateConfig

        configs = PrintTemplateConfig.objects.filter(user=self.user_without_perm)
        self.assertEqual(configs.count(), 0, "No config should be saved for user without permission")
