import os, sys
proj_root = os.path.dirname(os.path.dirname(__file__))
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)
print('sys.path[0]=', sys.path[0])
os.environ.setdefault('DJANGO_SETTINGS_MODULE','dashboard.settings')
from django import setup
setup()
from django.urls import get_resolver
r = get_resolver()
# collect names for 'accounting' namespace
ns_names = []
for key in r.reverse_dict.keys():
    if isinstance(key, str) and key.startswith('accounting:'):
        ns_names.append(key)
ns_names.sort()
print('\n'.join(ns_names))
print('Total accounting names:', len(ns_names))
