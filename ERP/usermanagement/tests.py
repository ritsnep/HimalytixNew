from django.test import TestCase
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from .models import CustomUser, Organization
from .utils import get_menu


class CustomUserTest(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Test Org", code="TST", type="company")
    def test_create_user(self):
        user = CustomUser.objects.create_user(username="testuser", password="pass", organization=self.org)
        self.assertEqual(user.username, "testuser")


class GetMenuTest(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Test Org", code="TST", type="company")
        self.user = CustomUser.objects.create_user(username="menuuser", password="pass", organization=self.org)
        ct = ContentType.objects.get_for_model(CustomUser)
        self.menu_perm = Permission.objects.create(codename="menu_dashboard", name="Dashboard", content_type=ct)
        self.other_perm = Permission.objects.create(codename="edit_dashboard", name="Edit Dashboard", content_type=ct)
        self.user.user_permissions.set([self.menu_perm, self.other_perm])

    def test_menu_generation(self):
        menu = get_menu(self.user)
        self.assertEqual(menu, [{"label": "Dashboard", "url": "dashboard"}])