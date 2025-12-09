import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard.settings')
from django import setup
setup()
from django.urls import get_resolver
p = get_resolver()
for entry in p.url_patterns:
    if getattr(entry, 'namespace', None) == 'accounting':
        print('FOUND ACCOUNTING include: pattern=', entry.pattern)
        try:
            sub = entry.url_patterns
            print('Subpatterns count:', len(sub))
            names = [sp.name for sp in sub if getattr(sp, 'name', None)]
            print('First 200 subpattern names:', names[:200])
        except Exception as e:
            import traceback
            traceback.print_exc()
