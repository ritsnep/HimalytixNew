#!/usr/bin/env python
"""Check delivery note URLs in accounting.urls"""
import os
import sys

sys.path.insert(0, 'C:\\PythonProjects\\Himalytix\\erp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp.settings')

import django
django.setup()

import accounting.urls as acc_urls

print(f"Total patterns: {len(acc_urls.urlpatterns)}")

delivery_patterns = []
for p in acc_urls.urlpatterns:
    route = str(p.pattern)
    if 'delivery' in route.lower():
        delivery_patterns.append((route, getattr(p, 'name', None)))

print(f"Delivery patterns: {delivery_patterns}")

# Try reverse
from django.urls import reverse
try:
    url = reverse('accounting:delivery_note_list')
    print(f"URL resolved: {url}")
except Exception as e:
    print(f"Error: {e}")
