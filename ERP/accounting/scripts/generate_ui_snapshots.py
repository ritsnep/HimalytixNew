import os
from django.utils.html import escape
from accounting.models import VoucherConfiguration
from accounting.forms_factory import VoucherFormFactory

OUT_DIR = os.path.join(os.getcwd(), 'accounting', 'ui_snapshots')
os.makedirs(OUT_DIR, exist_ok=True)

for cfg in VoucherConfiguration.objects.all():
    code = cfg.code
    try:
        factory = VoucherFormFactory(cfg.ui_schema)
        header_cls = factory.build_form()
        header = header_cls()
        header_html = header.as_p()
    except Exception as e:
        header_html = f"<!-- Error building header form: {escape(str(e))} -->"

    try:
        fs_cls = factory.build_formset(extra=1)
        fs = fs_cls()
        first_html = fs.forms[0].as_p() if fs.forms else '<!-- No forms produced -->'
    except Exception as e:
        first_html = f"<!-- Error building line formset: {escape(str(e))} -->"

    header_path = os.path.join(OUT_DIR, f"{code}_header.html")
    lines_path = os.path.join(OUT_DIR, f"{code}_lines.html")

    with open(header_path, 'w', encoding='utf-8') as hf:
        hf.write('<!doctype html>\n<html lang="en">\n<head><meta charset="utf-8"><title>Header - %s</title></head>\n<body>\n' % escape(code))
        hf.write('<h1>Header form for %s</h1>\n' % escape(code))
        hf.write(header_html)
        hf.write('\n</body></html>')

    with open(lines_path, 'w', encoding='utf-8') as lf:
        lf.write('<!doctype html>\n<html lang="en">\n<head><meta charset="utf-8"><title>Lines - %s</title></head>\n<body>\n' % escape(code))
        lf.write('<h1>Lines first form for %s</h1>\n' % escape(code))
        lf.write(first_html)
        lf.write('\n</body></html>')

    print(f"Wrote snapshots for {code}: header -> {header_path}, lines -> {lines_path}")