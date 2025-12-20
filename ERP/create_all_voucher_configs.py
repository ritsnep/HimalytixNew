#!/usr/bin/env python
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard.settings")
django.setup()

from accounting.services.voucher_seeding import seed_voucher_configs
from usermanagement.models import Organization


def create_all_voucher_configs():
    orgs = Organization.objects.all()
    if not orgs.exists():
        print("No organizations found!")
        return

    for org in orgs:
        print(f"Seeding voucher configurations for: {org.name}")
        seed_voucher_configs(org)

    print("All organizations seeded.")


if __name__ == "__main__":
    create_all_voucher_configs()
