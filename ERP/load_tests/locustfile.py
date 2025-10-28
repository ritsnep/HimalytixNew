from locust import HttpUser, task, between
import os
import random
import string
import json
from datetime import datetime, timedelta

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def random_text(n=12):
    return ''.join(random.choices(string.ascii_letters + string.digits + ' ', k=n)).strip()


def auth_headers():
    """Build authentication headers from environment or cached token."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "himalytix-locust/1.0",
    }
    api_key = os.getenv("LOCUST_API_KEY")
    if api_key:
        headers["Authorization"] = f"Api-Key {api_key}"
    return headers


class ERPUser(HttpUser):
    """
    Simulated ERP user performing common actions.

    Environment variables:
      - LOCUST_USERNAME: Username for JWT login (optional)
      - LOCUST_PASSWORD: Password for JWT login (optional)
      - LOCUST_API_KEY:  API key for header auth (optional)
      - LOCUST_TENANT_ID: Tenant context header (optional)
    """

    wait_time = between(1, 3)

    def on_start(self):
        self.headers = auth_headers()
        tenant_id = os.getenv("LOCUST_TENANT_ID")
        if tenant_id:
            self.headers["X-Tenant-ID"] = tenant_id

        # Obtain JWT if username/password provided and no API key
        if not self.headers.get("Authorization"):
            username = os.getenv("LOCUST_USERNAME")
            password = os.getenv("LOCUST_PASSWORD")
            if username and password:
                with self.client.post(
                    "/api/token/",
                    json={"username": username, "password": password},
                    headers=self.headers,
                    name="auth_token_obtain",
                    catch_response=True,
                ) as resp:
                    if resp.status_code == 200:
                        data = resp.json()
                        self.headers["Authorization"] = f"Bearer {data.get('access')}"
                        resp.success()
                    else:
                        resp.failure(f"JWT login failed: {resp.status_code}")

        # Keep some created IDs to operate on
        self._entry_ids = []

    # ------------------------------------------------------------------
    # BROWSE PAGES
    # ------------------------------------------------------------------
    @task(2)
    def view_dashboard(self):
        self.client.get("/dashboard/", headers=self.headers, name="ui_dashboard")

    @task(1)
    def view_home(self):
        self.client.get("/", headers=self.headers, name="ui_home")

    # ------------------------------------------------------------------
    # JOURNAL ENTRIES CRUD (API)
    # ------------------------------------------------------------------
    @task(3)
    def list_entries(self):
        params = {"page": 1, "page_size": 50}
        self.client.get(
            "/api/v1/journal-entries/",
            params=params,
            headers=self.headers,
            name="api_entries_list",
        )

    @task(2)
    def create_entry(self):
        payload = {
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "amount": round(random.uniform(10.0, 1000.0), 2),
            "description": f"LoadTest {random_text(16)}",
        }
        with self.client.post(
            "/api/v1/journal-entries/",
            data=json.dumps(payload),
            headers=self.headers,
            name="api_entries_create",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 201):
                try:
                    entry_id = resp.json().get("id")
                    if entry_id:
                        self._entry_ids.append(entry_id)
                except Exception:
                    pass
                resp.success()
            else:
                resp.failure(f"Create failed: {resp.status_code}")

    @task(2)
    def get_entry(self):
        if not self._entry_ids:
            return
        entry_id = random.choice(self._entry_ids)
        self.client.get(
            f"/api/v1/journal-entries/{entry_id}/",
            headers=self.headers,
            name="api_entries_get",
        )

    @task(1)
    def update_entry(self):
        if not self._entry_ids:
            return
        entry_id = random.choice(self._entry_ids)
        payload = {"description": f"Updated {random_text(8)}"}
        self.client.patch(
            f"/api/v1/journal-entries/{entry_id}/",
            data=json.dumps(payload),
            headers=self.headers,
            name="api_entries_update",
        )

    @task(1)
    def delete_entry(self):
        # Keep deletes infrequent
        if not self._entry_ids or random.random() < 0.8:
            return
        entry_id = self._entry_ids.pop(0)
        self.client.delete(
            f"/api/v1/journal-entries/{entry_id}/",
            headers=self.headers,
            name="api_entries_delete",
        )

    # ------------------------------------------------------------------
    # REPORTING / SEARCH (if available)
    # ------------------------------------------------------------------
    @task(1)
    def generate_report(self):
        self.client.get(
            "/api/v1/reports/monthly/",
            params={"format": "csv"},
            headers=self.headers,
            name="api_reports_monthly",
        )

    @task(1)
    def search(self):
        self.client.get(
            "/api/v1/search/",
            params={"q": random_text(6)},
            headers=self.headers,
            name="api_search",
        )
