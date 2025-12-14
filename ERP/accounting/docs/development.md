# Voucher Entry — Development & Local Testing

This document describes how to run and verify the voucher entry UI locally.

Prerequisites
- A working Python virtualenv with project dependencies installed (see repository `requirements.txt`).
- Access to a user that has `accounting.journal add` permission (admin is easiest during dev).

Start server

```powershell
cd c:\PythonProjects\Himalytix\ERP
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py runserver
```

Open the app
- Log in as a user with permission and navigate to: `/accounting/vouchers/new/` (or the project navigation link "Voucher Entry -> Voucher Entry New").

Quick test checklist
- Page loads with header, voucher header form, and empty grid.
- Click **Add First Line** — observe HTMX swap flash (if dev debug snippet is present) and verify a new row appears below column headers.
- Enter values in Description / Debit / Credit and blur the input — look for `POST /accounting/journal-entry/row/` in server logs and the console `htmx:afterRequest` messages.

Automated test example (Django test client)

You can simulate a logged-in post to add a row using Django's test client in a `manage.py shell` session:

```python
from django.test import Client
from django.contrib.auth import get_user_model
User = get_user_model()
admin = User.objects.filter(is_superuser=True).first()
c = Client()
c.force_login(admin)
r = c.post('/accounting/journal-entry/add-row/', {'line_count': '0'})
print(r.status_code)
print(r.content[:500])
```

Developer notes
- HTMX debug helpers were added to `voucher_entry_new.html` — they print debug messages and flash a small green indicator when swaps happen. Remove or disable in production.
- For visual testing, inspect the Network tab and look for the POST call to `/accounting/journal-entry/add-row/` and its HTML response.

