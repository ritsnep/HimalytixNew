"""
Auto-generate correctly-matching forms for all Inventory models
"""
import django
import os
import sys

sys.path.insert(0, os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ERP.settings')
django.setup()

from Inventory.models import (
    ProductCategory, Product, Warehouse, Location,
    PriceList, PriceListItem, CustomerPriceList, PromotionRule,
    PickList, PickListLine, PackingSlip, Shipment, Backorder, RMA
)

def get_model_fields(model):
    """Get all editable fields from a model (excluding auto fields, FK to Organization)"""
    fields = []
    for field in model._meta.get_fields():
        if hasattr(field, 'editable') and field.editable:
            # Skip organization FK (set in view)
            if field.name == 'organization':
                continue
            # Skip auto-generated fields
            if field.name in ('id', 'created_at', 'updated_at'):
                continue
            fields.append(field.name)
    return fields

models_to_check = [
    ('PromotionRule', PromotionRule),
    ('CustomerPriceList', CustomerPriceList),
    ('PickList', PickList),
    ('PickListLine', PickListLine),
    ('PackingSlip', PackingSlip),
    ('Shipment', Shipment),
    ('Backorder', Backorder),
    ('RMA', RMA),
]

print("=== Model Field Analysis ===\n")
for name, model in models_to_check:
    fields = get_model_fields(model)
    print(f"{name}: {', '.join(fields)}")
