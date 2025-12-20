#!/usr/bin/env python
"""Query all existing VoucherModeConfig records"""
import os
import sys
import django
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounting.models import VoucherModeConfig
import json

configs = VoucherModeConfig.objects.all().order_by('code')

print(f"\n{'='*80}")
print(f"EXISTING VOUCHERMODECONFIG RECORDS: {configs.count()}")
print(f"{'='*80}\n")

for config in configs:
    ui_schema = config.resolve_ui_schema() or {}
    header_fields = ui_schema.get('sections', {}).get('header', {}).get('fields', {})
    
    print(f"Code: {config.code}")
    print(f"Name: {config.name}")
    print(f"Active: {config.is_active}")
    print(f"UI Schema Fields: {len(header_fields)}")
    print(f"Description: {config.description or 'N/A'}")
    print(f"{'-'*80}\n")
