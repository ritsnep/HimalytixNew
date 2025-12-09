import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard.settings")

import django

django.setup()

from usermanagement.models import Organization, CustomUser
from django.test import Client

try:
    org, _ = Organization.objects.get_or_create(
        name="UI Test Org",
        defaults={"code": "UITEST", "type": "test"},
    )
except Exception as exc:
    import traceback

    print("Organization creation failed", type(exc), exc)
    traceback.print_exc()
    raise
user, created = CustomUser.objects.get_or_create(
    username="ui_tester",
    defaults={"full_name": "UI Tester", "email": "ui_tester@example.com", "role": "manager"},
)
if created:
    user.set_password("Password123!")
user.organization = org
user.save()
client = Client()
logged = client.login(username="ui_tester", password="Password123!")
response = client.get("/accounting/payable-dashboard/")
print("logged_in", logged)
print("status", response.status_code)
print("templates", response.template_name)
print("content_length", len(response.content))
if response.status_code != 200:
    print(response.content[:400].decode("utf-8", errors="ignore"))
