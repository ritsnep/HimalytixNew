from accounting.models import VoucherModeConfig
from accounting.forms_factory import VoucherFormFactory


def inspect_config(cfg):
    report = {'code': cfg.code, 'name': cfg.name, 'module': getattr(cfg, 'module', None), 'issues': [], 'header': {}, 'lines': {}}
    ui = cfg.resolve_ui_schema() or {}

    # Normalize sections
    for section in ('header', 'lines'):
        sec = ui.get(section)
        if sec is None:
            report[section] = {'present': False}
            continue
        report[section] = {'present': True}
        # Determine effective order
        if isinstance(sec, dict):
            explicit = sec.get('__order__')
            order = explicit if isinstance(explicit, list) else [k for k in sec.keys() if k != '__order__']
            items = [(name, sec.get(name)) for name in order]
            # Validate order_no consistency
            for idx, (name, cfg_item) in enumerate(items, start=1):
                if isinstance(cfg_item, dict) and 'order_no' in cfg_item and cfg_item.get('order_no') != idx:
                    report['issues'].append(f"{cfg.code}:{section}.{name} order_no {cfg_item.get('order_no')} != {idx}")
        elif isinstance(sec, list):
            items = list(sec)
            for idx, itm in enumerate(items, start=1):
                if isinstance(itm, dict) and 'order_no' in itm and itm.get('order_no') != idx:
                    report['issues'].append(f"{cfg.code}:{section}[{idx-1}] order_no {itm.get('order_no')} != {idx}")

    # Build header form and lines formset and check fields
    try:
        factory = VoucherFormFactory(cfg.resolve_ui_schema())
        header_form_cls = factory.build_form()
        header_form = header_form_cls()
        # Ensure header fields reflect ui schema header
        # (Check that fields in header section appear in the form unless hidden)
        header_ui = (cfg.resolve_ui_schema() or {}).get('header')
        if header_ui:
            names = []
            if isinstance(header_ui, dict):
                order = header_ui.get('__order__') or [k for k in header_ui.keys() if k != '__order__']
                names = order
            elif isinstance(header_ui, list):
                names = [it.get('name') or it.get('field') for it in header_ui]
            # Verify each non-hidden field exists in form
            for name in names:
                cfg_field = None
                if isinstance(header_ui, dict):
                    cfg_field = header_ui.get(name)
                else:
                    cfg_field = next((it for it in header_ui if (isinstance(it, dict) and (it.get('name') == name or it.get('field') == name))), None)
                if isinstance(cfg_field, dict) and cfg_field.get('hidden'):
                    continue
                if name not in header_form.base_fields:
                    report['issues'].append(f"{cfg.code}:header field {name} missing in header form")
                else:
                    w = header_form.base_fields[name].widget
                    attrs = getattr(w, 'attrs', {})
                    if 'form-control' not in (attrs.get('class') or ''):
                        report['issues'].append(f"{cfg.code}:header field {name} widget missing 'form-control' class")
    except Exception as e:
        report['issues'].append(f"{cfg.code}:header form build error: {e}")

    # Lines formset
    try:
        factory = VoucherFormFactory(cfg.resolve_ui_schema())
        FormSet = factory.build_formset(extra=0)
        fs = FormSet()
        first = fs.forms[0] if fs.forms else None
        lines_ui = (cfg.resolve_ui_schema() or {}).get('lines')
        if lines_ui and first is None:
            # When lines exist, we expect at least one form (extra=0 might produce zero). Rebuild with extra=1 to inspect fields
            FormSet = factory.build_formset(extra=1)
            fs = FormSet()
            first = fs.forms[0]
        if lines_ui:
            names = []
            if isinstance(lines_ui, dict):
                order = lines_ui.get('__order__') or [k for k in lines_ui.keys() if k != '__order__']
                names = order
            elif isinstance(lines_ui, list):
                names = [it.get('name') or it.get('field') for it in lines_ui]
            for name in names:
                # Skip hidden lines fields
                cfg_field = None
                if isinstance(lines_ui, dict):
                    cfg_field = lines_ui.get(name)
                else:
                    cfg_field = next((it for it in lines_ui if (isinstance(it, dict) and (it.get('name') == name or it.get('field') == name))), None)
                if isinstance(cfg_field, dict) and cfg_field.get('hidden'):
                    continue
                if first and name not in first.base_fields:
                    report['issues'].append(f"{cfg.code}:lines field {name} missing in line form")
                else:
                    if first:
                        w = first.base_fields[name].widget
                        attrs = getattr(w, 'attrs', {})
                        if 'form-control' not in (attrs.get('class') or ''):
                            report['issues'].append(f"{cfg.code}:lines field {name} widget missing 'form-control' class")
    except Exception as e:
        report['issues'].append(f"{cfg.code}:lines formset build error: {e}")

    return report


if __name__ == '__main__':
    reports = []
    for cfg in VoucherModeConfig.objects.all():
        r = inspect_config(cfg)
        reports.append(r)
    # Print summary
    total = len(reports)
    with_issues = [r for r in reports if r['issues']]
    print(f"Inspected {total} configurations, {len(with_issues)} with issues")
    for r in with_issues:
        print(f"- {r['code']}: {len(r['issues'])} issue(s)")
        for it in r['issues']:
            print(f"    * {it}")
    if not with_issues:
        print("All voucher UI schemas look consistent.")
