import json
import pprint

from accounting.models import VoucherConfiguration
from accounting.forms_factory import VoucherFormFactory

code = 'purchase_order'
cfg = VoucherConfiguration.objects.filter(code=code).first()
if not cfg:
    print('No VoucherConfiguration found for code:', code)
else:
    print('=== UI_SCHEMA ===')
    pprint.pprint(cfg.ui_schema or {})
    # Diagnostic: print types of header entries
    header = (cfg.ui_schema or {}).get('header')
    if isinstance(header, dict):
        print('\n--- Header entry types ---')
        for k, v in header.items():
            print(k, '->', type(v).__name__)
    else:
        print('\nHeader is not a dict; type:', type(header).__name__)
    print('\n=== HEADER FORM FIELDS (in order) ===')
    print('has resolve_ui_schema?:', hasattr(cfg, 'resolve_ui_schema'))
    if hasattr(cfg, 'resolve_ui_schema'):
        try:
            resolved = cfg.resolve_ui_schema()
            print('resolved type:', type(resolved).__name__)
            # print a small sample
            import itertools
            print('resolved (preview):')
            pprint.pprint(resolved if isinstance(resolved, (dict, list)) else str(resolved))
        except Exception as e:
            print('resolve_ui_schema error:', e)
    factory = VoucherFormFactory(configuration=cfg, organization=None)
    HeaderFormClass = factory.build_form()
    form = HeaderFormClass()
    for name, field in form.fields.items():
        attrs = getattr(field.widget, 'attrs', {})
        print(f"- {name} | field_class={field.__class__.__name__} | widget={field.widget.__class__.__name__} | attrs={attrs}")

    print('\n=== NOTE: Lines formset template can be inspected similarly if needed ===')
