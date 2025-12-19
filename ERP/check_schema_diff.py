import os
import django
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard.settings")
django.setup()

from accounting.models import VoucherConfiguration, SalesInvoice, SalesInvoiceLine
from django.db import models

def get_model_fields(model):
    return {f.name: f for f in model._meta.get_fields()}

def compare_schema_with_model(config_code, header_model, line_model):
    try:
        config = VoucherConfiguration.objects.get(code=config_code)
    except VoucherConfiguration.DoesNotExist:
        print(f"Config {config_code} not found")
        return

    ui_schema = config.ui_schema
    header_schema = ui_schema.get("header", {})
    lines_schema = ui_schema.get("lines", {})

    header_fields = get_model_fields(header_model)
    line_fields = get_model_fields(line_model)

    print(f"--- Comparing {config_code} ---")
    
    print("\nHeader Fields in Model but missing in Schema:")
    for field_name in header_fields:
        if field_name not in header_schema and not header_fields[field_name].auto_created:
            field = header_fields[field_name]
            if not field.is_relation or field.many_to_one:
                print(f"  - {field_name} ({type(field).__name__})")

    print("\nHeader Fields in Schema but missing in Model (or renamed):")
    for field_name in header_schema:
        if field_name not in header_fields:
            print(f"  - {field_name}")

    print("\nLine Fields in Model but missing in Schema:")
    for field_name in line_fields:
        if field_name not in lines_schema and not line_fields[field_name].auto_created:
            field = line_fields[field_name]
            if not field.is_relation or field.many_to_one:
                print(f"  - {field_name} ({type(field).__name__})")

    print("\nLine Fields in Schema but missing in Model (or renamed):")
    for field_name in lines_schema:
        if field_name not in line_fields:
            print(f"  - {field_name}")

if __name__ == "__main__":
    compare_schema_with_model("sales-invoice-vm-si", SalesInvoice, SalesInvoiceLine)
