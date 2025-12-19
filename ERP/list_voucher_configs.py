#!/usr/bin/env python
"""List all existing VoucherModeConfig records"""
import os
import sys
import django
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounting.models import VoucherModeConfig

configs = VoucherModeConfig.objects.all().order_by('code')

print(f"\nFound {configs.count()} VoucherModeConfig records:")
print("="*80)
print(f"  {'Code':<30} | {'Name':<40} | Active")
print("="*80)

for config in configs:
    status = "✓" if config.is_active else "✗"
    print(f"  {config.code:<30} | {config.name:<40} | {status}")

print()
