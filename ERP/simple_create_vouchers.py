#!/usr/bin/env python
"""
Simple script to create missing voucher configurations one at a time.
Uses schema_definition (single source of truth) instead of ui_schema.
"""
import os
import sys
import django
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from accounting.models import VoucherModeConfig
from accounting.voucher_schema import ui_schema_to_definition
from usermanagement.models import Organization


org = Organization.objects.first()
if not org:
    raise SystemExit("No organization found.")
print(f"Organization: {org.name}\n")


def get_ui_schema(fields_config):
    """Generate a standardized UI schema and convert later to definition."""
    return {
        "sections": {
            "header": {
                "__order__": [f["name"] for f in fields_config] + ["status"],
                "fields": {
                    **{f["name"]: f["config"] for f in fields_config},
                    "status": {
                        "order_no": 99,
                        "label": "Status",
                        "widget": "select",
                        "read_only": True,
                        "default": "draft",
                    },
                },
            }
        }
    }


VOUCHERS = [
    ("sales-invoice-vm-si", "Sales Invoice", "Sales invoice voucher", [
        {"name": "voucher_date", "config": {"order_no": 1, "autofocus": True, "label": "Date", "widget": "date", "required": True}},
        {"name": "customer", "config": {"order_no": 2, "label": "Customer", "widget": "typeahead", "required": True}},
        {"name": "reference_no", "config": {"order_no": 3, "label": "Ref No", "widget": "text"}},
    ]),
    ("journal-entry-vm-je", "Journal Entry", "General journal entry", [
        {"name": "voucher_date", "config": {"order_no": 1, "autofocus": True, "label": "Date", "widget": "date", "required": True}},
        {"name": "narration", "config": {"order_no": 2, "label": "Narration", "widget": "textarea", "required": True}},
    ]),
    ("VM-SI", "Sales Invoice (VM)", "Sales invoice VM", [
        {"name": "voucher_date", "config": {"order_no": 1, "autofocus": True, "label": "Date", "widget": "date", "required": True}},
        {"name": "customer", "config": {"order_no": 2, "label": "Customer", "widget": "typeahead", "required": True}},
    ]),
    ("VM-PI", "Purchase Invoice", "Purchase invoice", [
        {"name": "voucher_date", "config": {"order_no": 1, "autofocus": True, "label": "Date", "widget": "date", "required": True}},
        {"name": "vendor", "config": {"order_no": 2, "label": "Vendor", "widget": "typeahead", "required": True}},
    ]),
    ("VM-SO", "Sales Order", "Sales order", [
        {"name": "order_date", "config": {"order_no": 1, "autofocus": True, "label": "Order Date", "widget": "date", "required": True}},
        {"name": "customer", "config": {"order_no": 2, "label": "Customer", "widget": "typeahead", "required": True}},
    ]),
    ("VM-PO", "Purchase Order", "Purchase order", [
        {"name": "order_date", "config": {"order_no": 1, "autofocus": True, "label": "Order Date", "widget": "date", "required": True}},
        {"name": "vendor", "config": {"order_no": 2, "label": "Vendor", "widget": "typeahead", "required": True}},
    ]),
    ("VM-GR", "Goods Receipt", "Goods receipt", [
        {"name": "receipt_date", "config": {"order_no": 1, "autofocus": True, "label": "Receipt Date", "widget": "date", "required": True}},
        {"name": "vendor", "config": {"order_no": 2, "label": "Vendor", "widget": "typeahead", "required": True}},
    ]),
    ("VM-SCN", "Sales Credit Note", "Sales credit note", [
        {"name": "note_date", "config": {"order_no": 1, "autofocus": True, "label": "Date", "widget": "date", "required": True}},
        {"name": "customer", "config": {"order_no": 2, "label": "Customer", "widget": "typeahead", "required": True}},
    ]),
    ("VM-SDN", "Sales Debit Note", "Sales debit note", [
        {"name": "note_date", "config": {"order_no": 1, "autofocus": True, "label": "Date", "widget": "date", "required": True}},
        {"name": "customer", "config": {"order_no": 2, "label": "Customer", "widget": "typeahead", "required": True}},
    ]),
    ("VM-SR", "Sales Return", "Sales return", [
        {"name": "return_date", "config": {"order_no": 1, "autofocus": True, "label": "Date", "widget": "date", "required": True}},
        {"name": "customer", "config": {"order_no": 2, "label": "Customer", "widget": "typeahead", "required": True}},
    ]),
    ("VM-SQ", "Sales Quotation", "Sales quotation", [
        {"name": "quote_date", "config": {"order_no": 1, "autofocus": True, "label": "Date", "widget": "date", "required": True}},
        {"name": "customer", "config": {"order_no": 2, "label": "Customer", "widget": "typeahead", "required": True}},
    ]),
    ("VM-SD", "Sales Delivery", "Delivery note", [
        {"name": "delivery_date", "config": {"order_no": 1, "autofocus": True, "label": "Date", "widget": "date", "required": True}},
        {"name": "customer", "config": {"order_no": 2, "label": "Customer", "widget": "typeahead", "required": True}},
    ]),
    ("VM-PCN", "Purchase Credit Note", "Purchase credit note", [
        {"name": "note_date", "config": {"order_no": 1, "autofocus": True, "label": "Date", "widget": "date", "required": True}},
        {"name": "vendor", "config": {"order_no": 2, "label": "Vendor", "widget": "typeahead", "required": True}},
    ]),
    ("VM-PDN", "Purchase Debit Note", "Purchase debit note", [
        {"name": "note_date", "config": {"order_no": 1, "autofocus": True, "label": "Date", "widget": "date", "required": True}},
        {"name": "vendor", "config": {"order_no": 2, "label": "Vendor", "widget": "typeahead", "required": True}},
    ]),
    ("VM-PR", "Purchase Return", "Purchase return", [
        {"name": "return_date", "config": {"order_no": 1, "autofocus": True, "label": "Date", "widget": "date", "required": True}},
        {"name": "vendor", "config": {"order_no": 2, "label": "Vendor", "widget": "typeahead", "required": True}},
    ]),
    ("VM-LC", "Letter of Credit", "Letter of credit", [
        {"name": "lc_date", "config": {"order_no": 1, "autofocus": True, "label": "Date", "widget": "date", "required": True}},
        {"name": "bank", "config": {"order_no": 2, "label": "Bank", "widget": "text", "required": True}},
    ]),
]

created = 0
updated = 0

for code, name, description, fields in VOUCHERS:
    schema_definition = ui_schema_to_definition(get_ui_schema(fields))
    try:
        config = VoucherModeConfig.objects.get(code=code, organization=org)
        config.schema_definition = schema_definition
        config.name = name
        config.description = description
        config.save()
        print(f"Updated: {code}")
        updated += 1
    except VoucherModeConfig.DoesNotExist:
        VoucherModeConfig.objects.create(
            organization=org,
            code=code,
            name=name,
            description=description,
            schema_definition=schema_definition,
            is_active=True,
        )
        print(f"Created: {code}")
        created += 1
    except Exception as e:
        print(f"Error with {code}: {e}")

try:
    vm08 = VoucherModeConfig.objects.get(code="VM08", organization=org)
    vm08.schema_definition = ui_schema_to_definition(
        get_ui_schema([
            {"name": "voucher_date", "config": {"order_no": 1, "autofocus": True, "label": "Date", "widget": "date", "required": True}},
            {"name": "narration", "config": {"order_no": 2, "label": "Narration", "widget": "textarea", "required": True}},
        ])
    )
    vm08.save()
    print("Updated: VM08")
    updated += 1
except Exception as e:
    print(f"Error updating VM08: {e}")

print("\n" + "=" * 60)
print(f"Summary: Created {created}, Updated {updated}")
print(f"Total VoucherModeConfig: {VoucherModeConfig.objects.filter(organization=org).count()}")
print("=" * 60 + "\n")
