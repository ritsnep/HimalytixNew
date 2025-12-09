import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','dashboard.settings')
from django import setup
try:
    setup()
except Exception as e:
    import traceback; traceback.print_exc()

try:
    import importlib
    m = importlib.import_module('accounting.urls')
    print('Imported accounting.urls:', m)
    try:
        print('app_name:', getattr(m,'app_name',None))
        patterns = getattr(m, 'urlpatterns', [])
        print('pattern count:', len(patterns))
        for p in patterns[:200]:
            try:
                name = getattr(p, 'name', None)
                print('pattern:', p.pattern, 'name=', name)
            except Exception:
                import traceback; traceback.print_exc()
    except Exception:
        import traceback; traceback.print_exc()
except Exception as e:
    import traceback; traceback.print_exc()
