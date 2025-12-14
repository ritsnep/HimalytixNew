import os
import yaml

BASE_DIR = os.path.join(os.path.dirname(__file__), 'schemas')

_loaded = {}
from typing import Tuple


def load_voucher_schema(config) -> Tuple[dict, str, list]:
    """
    Load the schema YAML for the given config, with fallbacks.
    Returns (schema_dict, warning_str, tried_files_list)
    """
    import re
    schema = None
    warning = None
    tried_files = []
    schema_dir = os.path.join(os.path.dirname(__file__), 'views', 'schemas')

    # Try by code
    if getattr(config, 'code', None):
        code_file = os.path.join(schema_dir, f"{config.code.lower()}.yml")
        tried_files.append(code_file)
        if os.path.exists(code_file):
            with open(code_file, 'r', encoding='utf-8') as f:
                schema = yaml.safe_load(f) or {}

    # Try by name (slugified)
    if schema is None and getattr(config, 'name', None):
        slug = re.sub(r'[^a-z0-9_]+', '_', config.name.lower())
        name_file = os.path.join(schema_dir, f"{slug}.yml")
        tried_files.append(name_file)
        if os.path.exists(name_file):
            with open(name_file, 'r', encoding='utf-8') as f:
                schema = yaml.safe_load(f) or {}

    # Try fallback
    if schema is None:
        for fallback in ['general.yml', 'standard.yml']:
            fallback_file = os.path.join(schema_dir, fallback)
            tried_files.append(fallback_file)
            if os.path.exists(fallback_file):
                with open(fallback_file, 'r', encoding='utf-8') as f:
                    schema = yaml.safe_load(f) or {}
                    if schema:
                        break
    
    if schema is None:
        warning = f"No schema found for this voucher configuration. Tried: {', '.join(tried_files)}"
        
    return schema, warning, tried_files