#!/usr/bin/env python
"""
Debug script to test journal config endpoint and see what schema is returned
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from accounting.views.journal_entry import journal_config

User = get_user_model()

# Get first superuser
user = User.objects.filter(is_superuser=True).first()
if not user:
    print("No superuser found. Please create one first.")
    sys.exit(1)

# Create a fake request with config_id=1
factory = RequestFactory()
request = factory.get('/accounting/journal-entry/config/?config_id=1')
request.user = user

# Call the view
response = journal_config(request)

# Print the response
import json
if response.status_code == 200:
    data = json.loads(response.content)
    print("✓ Config endpoint returned successfully")
    print("\n=== Config Structure ===")
    config = data.get('config', {})
    print(f"Config ID: {config.get('id')}")
    print(f"Config Name: {config.get('name')}")
    
    ui_schema = config.get('uiSchema', {})
    print(f"\n=== Header Fields ({len(ui_schema.get('header', {}))}) ===")
    for key, field in ui_schema.get('header', {}).items():
        print(f"  {key}: {field.get('label')} ({field.get('type')})")
    
    print(f"\n=== Line Fields ({len(ui_schema.get('lines', {}))}) ===")
    for key, field in ui_schema.get('lines', {}).items():
        print(f"  {key}: {field.get('label')} ({field.get('type')})")
    
    print(f"\n=== UDF Definitions ===")
    udf = config.get('udf', {})
    print(f"  Header UDFs: {len(udf.get('header', []))}")
    print(f"  Line UDFs: {len(udf.get('line', []))}")
    
    print(f"\n=== Metadata ===")
    metadata = config.get('metadata', {})
    print(f"  Journal Type: {metadata.get('journalTypeCode')}")
    print(f"  Default Currency: {metadata.get('defaultCurrency')}")
    print(f"  Header Required: {metadata.get('headerRequired', [])}")
    print(f"  Line Required: {metadata.get('lineRequired', [])}")
    
else:
    print(f"✗ Config endpoint failed: {response.status_code}")
    print(response.content.decode())
