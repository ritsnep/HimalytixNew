import os, sys
proj_root = os.path.dirname(os.path.dirname(__file__))
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)
print('sys.path[0]=', sys.path[0])
try:
    import importlib
    m = importlib.import_module('accounting.urls')
    print('Imported accounting.urls successfully')
    print('app_name', getattr(m, 'app_name', None))
    print('URL patterns count', len(getattr(m, 'urlpatterns', [])))
except Exception as e:
    import traceback; traceback.print_exc()
