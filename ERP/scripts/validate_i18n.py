import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

I18N_FILES = [
    ROOT / 'i18n' / 'en.json',
    ROOT / 'accounting' / 'i18n' / 'en.json',
]

TEMPLATE_DIRS = [
    ROOT / 'templates',
    ROOT / 'accounting' / 'templates',
]

JS_DIRS = [
    ROOT / 'accounting' / 'static' / 'accounting' / 'js',
]

def load_keys():
    keys = set()
    for f in I18N_FILES:
        if f.exists():
            # Handle files with/without BOM
            data = json.loads(f.read_text(encoding='utf-8-sig'))
            keys.update(data.keys())
    return keys

def find_used_keys():
    used = set()
    # Matches i18n["foo.bar"] or i18n['foo.bar'] or i18n.key_underscore
    re_bracket = re.compile(r"i18n\[[\"']([\w\.-]+)[\"']\]")
    re_dot = re.compile(r"\{\{\s*i18n\.([a-zA-Z0-9_]+)\s*\|?")
    re_filter = re.compile(r"i18n\|i18n_get:[\"']([\w\.-]+)[\"']")

    def scan_file(path):
        text = path.read_text(encoding='utf-8', errors='ignore')
        used.update(re_bracket.findall(text))
        used.update(re_filter.findall(text))
        used.update(re_dot.findall(text))

    for base in TEMPLATE_DIRS:
        for root, _, files in os.walk(base):
            for name in files:
                if name.endswith(('.html', '.txt')):
                    scan_file(Path(root) / name)
    for base in JS_DIRS:
        for root, _, files in os.walk(base):
            for name in files:
                if name.endswith('.js'):
                    # Look for t('key') usages
                    path = Path(root) / name
                    text = path.read_text(encoding='utf-8', errors='ignore')
                    for m in re.finditer(r"\bt\(\s*[\"']([\w\.-]+)[\"']\s*\)", text):
                        used.add(m.group(1))
    return used

def main():
    keys = load_keys()
    used = find_used_keys()
    missing = sorted([k for k in used if k not in keys])
    unused = sorted([k for k in keys if k not in used])

    print("Missing keys (used in code/templates but not in en.json):")
    for k in missing:
        print("  ", k)
    print("\nUnused keys (present in en.json but not referenced):")
    for k in unused:
        print("  ", k)

if __name__ == '__main__':
    main()
