
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard.settings")
django.setup()

from django.db import connection

# Reset any stale connections 
connection.close()

from django.core.management import call_command
import traceback

try:
    print("Running seed_voucher_demo...")
    call_command("seed_voucher_demo")
    print("Success!")
except Exception:
    print("Failed! Writing traceback to debug_error.log")
    with open("debug_error.log", "w") as f:
        traceback.print_exc(file=f)
    traceback.print_exc()
