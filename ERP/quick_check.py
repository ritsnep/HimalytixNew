import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from accounting.models import VoucherModeConfig

codes = [
    "sales-invoice-vm-si", "VM08", "journal-entry-vm-je", "VM-SI", "VM-PI",
    "VM-SO", "VM-PO", "VM-GR", "VM-SCN", "VM-SDN", "VM-SR", "VM-SQ",
    "VM-SD", "VM-PCN", "VM-PDN", "VM-PR", "VM-LC"
]

print(f"Total VoucherModeConfig records: {VoucherModeConfig.objects.count()}")
print(f"\nTarget codes: {len(codes)}")
print("-" * 60)

for code in codes:
    exists = VoucherModeConfig.objects.filter(code=code).exists()
    if exists:
        config = VoucherModeConfig.objects.get(code=code)
        ui_fields = len(config.resolve_ui_schema().get("sections", {}).get("header", {}).get("fields", {}))
        print(f"{code:25} | Fields: {ui_fields}")
    else:
        print(f"{code:25} | NOT FOUND")
