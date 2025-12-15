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
            "header": {
                "__order__": ["supplier", "order_date", "expected_delivery_date", "terms", "notes"],
                "supplier": {"label": "Supplier", "type": "select", "placeholder": "Select Supplier", "order_no": 1},
                "order_date": {"label": "Order Date", "type": "date", "order_no": 2},
                "expected_delivery_date": {"label": "Expected Delivery Date", "type": "date", "order_no": 3},
                "terms": {"label": "Terms", "type": "text", "order_no": 4},
                "notes": {"label": "Notes", "type": "text", "order_no": 5}
            },
            "lines": [
                {"name": "item", "label": "Item", "type": "char", "order_no": 1},
                {"name": "quantity", "label": "Quantity", "type": "integer", "order_no": 2},
                {"name": "unit_price", "label": "Unit Price", "type": "decimal", "order_no": 3}
            ]
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
            "header": {
                "__order__": ["customer", "order_date", "delivery_date", "payment_terms", "notes"],
                "customer": {"label": "Customer", "type": "select", "placeholder": "Select Customer", "order_no": 1},
                "order_date": {"label": "Order Date", "type": "date", "order_no": 2},
                "delivery_date": {"label": "Delivery Date", "type": "date", "order_no": 3},
                "payment_terms": {"label": "Payment Terms", "type": "text", "order_no": 4},
                "notes": {"label": "Notes", "type": "text", "order_no": 5}
            },
            "lines": [
                {"name": "item", "label": "Item", "type": "char", "order_no": 1},
                {"name": "quantity", "label": "Quantity", "type": "integer", "order_no": 2},
                {"name": "price", "label": "Price", "type": "decimal", "order_no": 3}
            ]
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
            "header": {
                "__order__": ["supplier", "return_date", "original_invoice", "reason", "notes"],
                "supplier": {"label": "Supplier", "type": "select", "placeholder": "Select Supplier", "order_no": 1},
                "return_date": {"label": "Return Date", "type": "date", "order_no": 2},
                "original_invoice": {"label": "Original Invoice", "type": "char", "placeholder": "Original Invoice Number", "order_no": 3},
                "reason": {"label": "Reason", "type": "select", "choices": [["damaged","Damaged Goods"],["wrong_item","Wrong Item"],["quality_issue","Quality Issue"],["other","Other"]], "order_no": 4},
                "notes": {"label": "Notes", "type": "text", "order_no": 5}
            },
            "lines": [
                {"name": "item", "label": "Item", "type": "char", "order_no": 1},
                {"name": "qty", "label": "Quantity", "type": "integer", "order_no": 2}
            ]
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