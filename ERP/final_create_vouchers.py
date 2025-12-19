#!/usr/bin/env python
"""
Final script to create ALL 17 target vouchers
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from accounting.models import VoucherModeConfig
from usermanagement.models import Organization

org = Organization.objects.first()
print(f"Organization: {org.name}\n", flush=True)

# Standard UI schema generator
def make_ui_schema(field_defs):
    """Create standardized ui_schema with ordering, autofocus, status"""
    field_names = [f['name'] for f in field_defs]
    fields = {}
    
    for i, field_def in enumerate(field_defs, 1):
        fields[field_def['name']] = {
            'order_no': i,
            'autofocus': (i == 1),
            'label': field_def['label'],
            'widget': field_def.get('widget', 'text'),
            'required': field_def.get('required', True)
        }
        if 'lookup_url' in field_def:
            fields[field_def['name']]['lookup_url'] = field_def['lookup_url']
    
    # Add status field
    fields['status'] = {
        'order_no': 99,
        'label': 'Status',
        'widget': 'select',
        'read_only': True,
        'default': 'draft'
    }
    
    return {
        'sections': {
            'header': {
                '__order__': field_names + ['status'],
                'fields': fields
            }
        }
    }

# Define all 17 vouchers with minimal configuration
VOUCHERS = [
    ('sales-invoice-vm-si', 'Sales Invoice', 'Sales invoice voucher', [
        {'name': 'voucher_date', 'label': 'Date', 'widget': 'date'},
        {'name': 'customer', 'label': 'Customer', 'widget': 'typeahead', 'lookup_url': 'accounting:generic_voucher_customer_lookup_hx'},
        {'name': 'reference_no', 'label': 'Ref No', 'required': False}
    ]),
    ('journal-entry-vm-je', 'Journal Entry', 'General journal entry', [
        {'name': 'voucher_date', 'label': 'Date', 'widget': 'date'},
        {'name': 'narration', 'label': 'Narration', 'widget': 'textarea'}
    ]),
    ('VM-SI', 'Sales Invoice (VM)', 'Sales invoice VM', [
        {'name': 'voucher_date', 'label': 'Date', 'widget': 'date'},
        {'name': 'customer', 'label': 'Customer', 'widget': 'typeahead'}
    ]),
    ('VM-PI', 'Purchase Invoice', 'Purchase invoice', [
        {'name': 'voucher_date', 'label': 'Date', 'widget': 'date'},
        {'name': 'vendor', 'label': 'Vendor', 'widget': 'typeahead'}
    ]),
    ('VM-SO', 'Sales Order', 'Sales order', [
        {'name': 'order_date', 'label': 'Order Date', 'widget': 'date'},
        {'name': 'customer', 'label': 'Customer', 'widget': 'typeahead'}
    ]),
    ('VM-PO', 'Purchase Order', 'Purchase order', [
        {'name': 'order_date', 'label': 'Order Date', 'widget': 'date'},
        {'name': 'vendor', 'label': 'Vendor', 'widget': 'typeahead'}
    ]),
    ('VM-GR', 'Goods Receipt', 'Goods receipt', [
        {'name': 'receipt_date', 'label': 'Receipt Date', 'widget': 'date'},
        {'name': 'vendor', 'label': 'Vendor', 'widget': 'typeahead'}
    ]),
    ('VM-SCN', 'Sales Credit Note', 'Sales credit note', [
        {'name': 'note_date', 'label': 'Date', 'widget': 'date'},
        {'name': 'customer', 'label': 'Customer', 'widget': 'typeahead'}
    ]),
    ('VM-SDN', 'Sales Debit Note', 'Sales debit note', [
        {'name': 'note_date', 'label': 'Date', 'widget': 'date'},
        {'name': 'customer', 'label': 'Customer', 'widget': 'typeahead'}
    ]),
    ('VM-SR', 'Sales Return', 'Sales return', [
        {'name': 'return_date', 'label': 'Date', 'widget': 'date'},
        {'name': 'customer', 'label': 'Customer', 'widget': 'typeahead'}
    ]),
    ('VM-SQ', 'Sales Quotation', 'Sales quotation', [
        {'name': 'quote_date', 'label': 'Date', 'widget': 'date'},
        {'name': 'customer', 'label': 'Customer', 'widget': 'typeahead'}
    ]),
    ('VM-SD', 'Sales Delivery', 'Delivery note', [
        {'name': 'delivery_date', 'label': 'Date', 'widget': 'date'},
        {'name': 'customer', 'label': 'Customer', 'widget': 'typeahead'}
    ]),
    ('VM-PCN', 'Purchase Credit Note', 'Purchase credit note', [
        {'name': 'note_date', 'label': 'Date', 'widget': 'date'},
        {'name': 'vendor', 'label': 'Vendor', 'widget': 'typeahead'}
    ]),
    ('VM-PDN', 'Purchase Debit Note', 'Purchase debit note', [
        {'name': 'note_date', 'label': 'Date', 'widget': 'date'},
        {'name': 'vendor', 'label': 'Vendor', 'widget': 'typeahead'}
    ]),
    ('VM-PR', 'Purchase Return', 'Purchase return', [
        {'name': 'return_date', 'label': 'Date', 'widget': 'date'},
        {'name': 'vendor', 'label': 'Vendor', 'widget': 'typeahead'}
    ]),
    ('VM-LC', 'Letter of Credit', 'Letter of credit', [
        {'name': 'lc_date', 'label': 'Date', 'widget': 'date'},
        {'name': 'bank', 'label': 'Bank', 'widget': 'text'}
    ]),
]

created = 0
updated = 0
errors = 0

# Process each voucher
for code, name, description, fields in VOUCHERS:
    try:
        existing = VoucherModeConfig.objects.filter(code=code, organization=org).first()
        
        if existing:
            existing.ui_schema = make_ui_schema(fields)
            existing.name = name
            existing.description = description
            existing.save()
            print(f"✓ Updated: {code}", flush=True)
            updated += 1
        else:
            VoucherModeConfig.objects.create(
                organization=org,
                code=code,
                name=name,
                description=description,
                ui_schema=make_ui_schema(fields),
                is_active=True
            )
            print(f"✓ Created: {code}", flush=True)
            created += 1
    except Exception as e:
        print(f"✗ Error with {code}: {e}", flush=True)
        errors += 1

# Update VM08 as well
try:
    vm08 = VoucherModeConfig.objects.get(code='VM08', organization=org)
    vm08.ui_schema = make_ui_schema([
        {'name': 'voucher_date', 'label': 'Date', 'widget': 'date'},
        {'name': 'narration', 'label': 'Narration', 'widget': 'textarea'}
    ])
    vm08.save()
    print(f"✓ Updated: VM08")
    updated += 1
except Exception as e:
    print(f"✗ Error updating VM08: {e}")
    errors += 1

print(f"\n{'='*60}")
print(f"Created: {created}")
print(f"Updated: {updated}")
print(f"Errors: {errors}")
print(f"Total VoucherModeConfig: {VoucherModeConfig.objects.filter(organization=org).count()}")
print(f"{'='*60}\n")
