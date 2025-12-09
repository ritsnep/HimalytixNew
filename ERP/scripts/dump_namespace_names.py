import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','dashboard.settings')
from django import setup
setup()
from django.urls import get_resolver
r=get_resolver()
for k in sorted([k for k in r.reverse_dict.keys() if isinstance(k,str) and k.startswith('accounting')]):
    print(k)
