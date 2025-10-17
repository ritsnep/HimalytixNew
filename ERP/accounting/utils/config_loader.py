import json
import yaml
import os
from django.conf import settings

def get_config_path(filename):
    return os.path.join(settings.BASE_DIR, 'accounting', 'config', filename)

def get_i18n_path(filename):
    return os.path.join(settings.BASE_DIR, 'accounting', 'i18n', filename)

def load_ui_config():
    """Loads the UI configuration from ui.json."""
    with open(get_config_path('ui.json'), 'r') as f:
        return json.load(f)

def load_validation_config():
    """Loads the validation rules from validation.json."""
    with open(get_config_path('validation.json'), 'r') as f:
        return json.load(f)

def load_workflow_config():
    """Loads the workflow definition from workflow.yml."""
    try:
        with open(get_config_path('workflow.yml'), 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        # Fallback to .yaml if .yml is not found
        with open(get_config_path('workflow.yaml'), 'r') as f:
            return yaml.safe_load(f)

def load_i18n_strings(lang_code='en'):
    """Loads the internationalization strings for a given language."""
    with open(get_i18n_path(f'{lang_code}.json'), 'r', encoding='utf-8') as f:
        return json.load(f)