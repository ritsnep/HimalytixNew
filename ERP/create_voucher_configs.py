#!/usr/bin/env python
import os
import django
import json

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard.settings')
django.setup()

from accounting.models import VoucherConfiguration, Organization

def create_voucher_configs():
    # Get the first organization (assuming there's at least one)
    org = Organization.objects.first()
    if not org:
        print("No organization found!")
        return

    print(f"Using organization: {org.name}")

    # Purchase Order Configuration
    purchase_order_config = {
        "code": "purchase_order",
        "name": "Purchase Order",
        "module": "purchasing",
        "description": "Purchase Order Voucher",
        "is_active": True,
        "organization": org,
        "ui_schema": {
            "supplier": {
                "ui:widget": "select",
                "ui:placeholder": "Select Supplier"
            },
            "order_date": {
                "ui:widget": "date"
            },
            "expected_delivery_date": {
                "ui:widget": "date"
            },
            "terms": {
                "ui:widget": "textarea"
            },
            "notes": {
                "ui:widget": "textarea"
            }
        },
        "default_header": {
            "order_date": "today"
        }
    }

    # Sales Order Configuration
    sales_order_config = {
        "code": "sales_order",
        "name": "Sales Order",
        "module": "sales",
        "description": "Sales Order Voucher",
        "is_active": True,
        "organization": org,
        "ui_schema": {
            "customer": {
                "ui:widget": "select",
                "ui:placeholder": "Select Customer"
            },
            "order_date": {
                "ui:widget": "date"
            },
            "delivery_date": {
                "ui:widget": "date"
            },
            "payment_terms": {
                "ui:widget": "textarea"
            },
            "notes": {
                "ui:widget": "textarea"
            }
        },
        "default_header": {
            "order_date": "today"
        }
    }

    # Purchase Return Configuration
    purchase_return_config = {
        "code": "purchase_return",
        "name": "Purchase Return",
        "module": "purchasing",
        "description": "Purchase Return Voucher",
        "is_active": True,
        "organization": org,
        "ui_schema": {
            "supplier": {
                "ui:widget": "select",
                "ui:placeholder": "Select Supplier"
            },
            "return_date": {
                "ui:widget": "date"
            },
            "original_invoice": {
                "ui:widget": "text",
                "ui:placeholder": "Original Invoice Number"
            },
            "reason": {
                "ui:widget": "select",
                "ui:options": [
                    {"value": "damaged", "label": "Damaged Goods"},
                    {"value": "wrong_item", "label": "Wrong Item"},
                    {"value": "quality_issue", "label": "Quality Issue"},
                    {"value": "other", "label": "Other"}
                ]
            },
            "notes": {
                "ui:widget": "textarea"
            }
        },
        "default_header": {
            "return_date": "today"
        }
    }

    # Create the configurations
    configs = [purchase_order_config, sales_order_config, purchase_return_config]

    for config_data in configs:
        config, created = VoucherConfiguration.objects.get_or_create(
            code=config_data["code"],
            organization=config_data["organization"],
            defaults=config_data
        )
        if created:
            print(f"Created {config.name} configuration")
        else:
            print(f"{config.name} configuration already exists")

    print("All configurations created successfully!")

if __name__ == "__main__":
    create_voucher_configs()