import json
import pprint

from accounting.models import VoucherConfiguration
from accounting.forms_factory import VoucherFormFactory

code = 'purchase_order'
cfg = VoucherConfiguration.objects.filter(code=code).first()
if not cfg:
    print('No VoucherConfiguration found for code:', code)
else:
    print('=== UI_SCHEMA (lines section) ===')
    ui = cfg.ui_schema or {}
    lines_schema = ui.get('lines')
    pprint.pprint(lines_schema)

    print('\n=== LINES FORMSET FIELDS (in order) ===')
    factory = VoucherFormFactory(configuration=cfg, organization=None)
    LineFormsetClass = factory.build_formset()
    formset = LineFormsetClass()
    # Inspect the first form in the formset
    if formset.forms:
        form = formset.forms[0]
        for name, field in form.fields.items():
            attrs = getattr(field.widget, 'attrs', {})
            print(f"- {name} | field_class={field.__class__.__name__} | widget={field.widget.__class__.__name__} | attrs={attrs}")
    else:
        print('No forms in formset')

    print('\n=== NOTE: This inspects the first line form in the formset ===')