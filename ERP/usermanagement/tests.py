from django.test import TestCase
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from .models import CustomUser, Organization
from .models import UserOrganization
from .utils import get_menu
from django.urls import reverse
from django.test import Client


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


class SelectOrganizationViewTest(TestCase):
    def setUp(self):
        self.org1 = Organization.objects.create(name="Org One", code="ORG1", type="company")
        self.org2 = Organization.objects.create(name="Org Two", code="ORG2", type="company")
        self.user = CustomUser.objects.create_user(username="orguser", password="pass", organization=self.org1)
        UserOrganization.objects.create(user=self.user, organization=self.org1, is_active=True)
        UserOrganization.objects.create(user=self.user, organization=self.org2, is_active=True)
        self.client = Client()
        self.client.force_login(self.user)

    def test_get_shows_active_selected(self):
        response = self.client.get(reverse('usermanagement:select_organization'))
        # active organization is org1 by membership and user's organization
        self.assertContains(response, f'value="{self.org1.id}" selected', status_code=200)

    def test_post_sets_session_active_org(self):
        resp = self.client.post(reverse('usermanagement:select_organization'), {'organization': str(self.org2.id)})
        # should redirect on success
        self.assertIn(resp.status_code, (302, 303))
        # check session set
        session = self.client.session
        self.assertEqual(session.get('active_organization_id'), self.org2.id)