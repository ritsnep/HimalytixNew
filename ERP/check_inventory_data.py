#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from inventory.models import ProductCategory, Product, Warehouse, Location
from tenancy.models import Organization

# Get the first organization or create one for testing
org = Organization.objects.first()
print(f"Testing with organization: {org}")

# Check data counts
print(f"\nData counts for {org}:")
print(f"ProductCategory count: {ProductCategory.objects.filter(organization=org).count()}")
print(f"Product count: {Product.objects.filter(organization=org).count()}")
print(f"Warehouse count: {Warehouse.objects.filter(organization=org).count()}")
print(f"Location count: {Location.objects.filter(organization=org).count()}")

# List sample categories
cats = ProductCategory.objects.filter(organization=org)[:5]
print(f"\nSample ProductCategories:")
if cats.exists():
    for cat in cats:
        print(f"  - {cat.name}")
else:
    print("  No categories found!")

# Check if views can access the data
from inventory.views import ProductCategoryListView
print(f"\nProductCategoryListView model: {ProductCategoryListView.model}")
print(f"ProductCategoryListView queryset: {ProductCategoryListView().get_queryset()}")
