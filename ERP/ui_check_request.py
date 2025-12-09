import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard.settings")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "testserver,127.0.0.1,localhost")

import django

django.setup()

from django.test import Client

client = Client()
response = client.get("/accounting/payable-dashboard/")
print("status_code", response.status_code)
if response.status_code != 200:
    print("response snippet:", response.content[:400].decode("utf-8", errors="ignore"))
if hasattr(response, "redirect_chain"):
    print("redirect_chain", response.redirect_chain)
else:
    print("redirect_chain", [])
print("final_url", getattr(response, "url", ""))
