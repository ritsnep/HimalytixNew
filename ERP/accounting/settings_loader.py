import json, os
from django.conf import settings
from datetime import datetime

SETTINGS_PATH = os.path.join(settings.BASE_DIR, "ERP/accounting/settings/voucher_settings.json")
AUDIT_PATH = os.path.join(settings.BASE_DIR, "ERP/accounting/settings/audit/")

DEFAULT_SETTINGS = {
    "version": 1,
    "fields": {
        "header": {
            "date": {"required": True, "type": "date", "help": "Transaction date"},
            "reference": {"required": False, "type": "string", "regex": "^[A-Z0-9-]*$", "help": "Alphanumeric, optional"}
        },
        "lines": {
            "account": {"required": True, "type": "account", "help": "GL Account"},
            "amount": {"required": True, "type": "decimal", "min": 0.01, "help": "Debit or credit amount"}
        }
    },
    "rules": [
        {"if": {"<": [{"var": "amount"}, 0]}, "then": {"error": "Amount must be positive"}, "priority": 1, "enabled": True}
    ],
    "feature_flags": {
        "enable_custom_hooks": False,
        "enable_diff_preview": True
    }
}

def ensure_settings_file():
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    os.makedirs(AUDIT_PATH, exist_ok=True)
    if not os.path.exists(SETTINGS_PATH):
        with open(SETTINGS_PATH, "w") as f:
            json.dump(DEFAULT_SETTINGS, f, indent=2)

def load_settings():
    ensure_settings_file()
    with open(SETTINGS_PATH) as f:
        return json.load(f)

def save_settings(new_settings, user):
    # Save old version to audit, then write new
    now = datetime.now().strftime("%Y%m%d%H%M%S")
    with open(SETTINGS_PATH) as f:
        old = f.read()
    with open(os.path.join(AUDIT_PATH, f"settings_{now}.json"), "w") as f:
        f.write(old)
    with open(SETTINGS_PATH, "w") as f:
        f.write(new_settings)
    # Optionally log user info

def get_audit_trail():
    # Return list of changes
    return os.listdir(AUDIT_PATH)

def preview_diff(new_settings):
    import difflib
    with open(SETTINGS_PATH) as f:
        old = f.read().splitlines()
    new = new_settings.splitlines()
    return '\n'.join(difflib.unified_diff(old, new, fromfile='current', tofile='new'))

def rollback_settings():
    files = sorted(os.listdir(AUDIT_PATH), reverse=True)
    if files:
        with open(os.path.join(AUDIT_PATH, files[0])) as f:
            prev = f.read()
        with open(SETTINGS_PATH, "w") as f:
            f.write(prev)

def validate_settings(settings_json):
    try:
        data = json.loads(settings_json)
        # Add more validation as needed
        return True, []
    except Exception as e:
        return False, [str(e)]
