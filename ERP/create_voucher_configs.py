#!/usr/bin/env python
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard.settings")
django.setup()

from accounting.services.voucher_seeding import seed_voucher_configs
from usermanagement.models import Organization


def create_voucher_configs():
    org = Organization.objects.first()
    if not org:
        print("No organization found!")
        return

    print(f"Seeding voucher configurations for: {org.name}")
    seed_voucher_configs(org)
    print("Seeding complete.")


if __name__ == "__main__":
    create_voucher_configs()
